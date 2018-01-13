import threading
import logging
import functools
import sys
import traceback

logger = logging.getLogger('easync')

PY3 = sys.version_info >= (3, 0)


def log_exception(exception, exc_info=sys.exc_info(), level=logging.WARNING):
    """
    Exception formatter and logger.

    Logs a caught exception into the `logging` according to logging configs and exception handling.
    Unlike `logging.Logger`, this will output stack trace in the reverse way (easier to look) and with better
    readability (for C coders).
    Also, prints out thread information, because this is very useful in massively threaded case.

    :param (Exception) exception:
    :param exc_info: Optional, the output of the ``sys.exc_info()``, if it was caught earlier.
    :param level: Optional, the desired level of the logging.
    """
    try:
        tb = list(reversed(traceback.extract_tb(exc_info[2])))

        tb_str = '\n'
        for i in tb:
            tb_str += '{file}:{line} (in {module}): {call}\n'.format(file=i[0],
                                                                     line=i[1],
                                                                     module=i[2],
                                                                     call=i[3])
        thread = threading.currentThread()
        msg = '%s: %s' % (type(exception).__name__, exception.message)
        msg += '\nTraceback: (latest call first)' + tb_str + 'Thread: %s(%d)' % (thread.getName(), thread.ident)

        logger.handle(logger.makeRecord(logger.name, level, tb[0][0], tb[0][1], msg, (), None, tb[0][2]))
    except Exception as e:
        logger.warn("Could not make an exception trace for exception: %s" % exception.message)
        logger.warn("Caught exeption: %s" % e.message)


def _has_methods(obj, *methods):
    """
    For ducktype testers.
    Tests for methods to exist on objects.
    :param obj:
    :param methods: (variadic)
    :return:
    """
    for method in methods:
        if not hasattr(obj, method) or not callable(getattr(obj, method)):
            return False
    return True


def _is_waitable(obj):
    """
    Ducktype-tester for `threading.Condition` or `threading.Event` type.
    :param obj:
    :return: boolean
    """
    return _has_methods(obj, 'wait')


def _get_first_of(obj, *args):
    """
    Helper function, returns first existing property of the object that is not None.
    :param obj:
    :param args: variadic, names of the properties
    :return:
    """
    for arg in args:
        if hasattr(obj, arg):
            prop = getattr(obj, arg)
            if prop is not None:
                return prop

    return None


def is_failed(ev):
    """
    Returns failure of the `threading.Event` or `threading.Condition` if they were supplied through the properties of
    the object.
    If no failure supplied, `None` is returned.
    :param ev: `threading.Event` or `threading.Condition`
    :return:
    """
    error = _get_first_of(ev, 'exception', 'error', 'failure')
    if error is not None:
        return error

    if _get_first_of(ev, 'failed', 'is_failed'):
        return True

    s = _get_first_of(ev, 'success')
    if s is not None and not s:
        return True

    return None


def get_result(ev):
    """
    Returns result of the `threading.Event` or `threading.Condition` if they were supplied through the properties of
    the object.
    If no result supplied, `None` is returned.
    :param ev: `threading.Event` or `threading.Condition`
    :return:
    """
    return _get_first_of(ev, 'result', 'success')


class TimeoutError(RuntimeError):
    """
    Raised during wait, if timeout reached.
    """
    pass


class Promise(threading.Thread):
    """
    This is a threading wrapper that performs asynchronous call of the provided function.

    Basic usage:

    .. code-block:: python

        promise = Promise(func)(...__args)
        result = promise.wait()
        #  or
        result = Promise(func)(...__args).wait()

        #  callbacks
        def callback(result):
            print result
        def exception_catcher(exception):
            log(exception)
        def some_final(_):
            cleanup()

        Promise(func)(...__args).then(callback, exception_catcher).then(some_final)

    For advanced usage, see https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Promise
    It is close to that document, though functions in Promises can use any arguments and should be started manually.
    Rejections thus are based on exceptions and resolutions are simply function results.
    """
    Callable = None

    started = None
    resolved = None
    result = None
    exception = None
    exc_info = None
    print_exception = None

    __args = None
    __kwargs = None

    def __init__(self, function=None, daemon=False, print_exception=logging.ERROR):
        """
        Saves function, it's callback and daemon state.

        :param function: The function to call.
        :param Boolean daemon: Whether the thread is a daemon.
                               Daemon threads die automatically when no other threads are left.
        :param print_exception: Log level to output the exception, or `None` to mute it. See `logging`.
        """
        super(Promise, self).__init__()
        self.print_exception = print_exception
        self.Callable = function
        self.daemon = daemon
        self.__resolve_name()
        self.started = threading.Event()
        self.finished = threading.Event()

        self.__check_callable()

    def __check_callable(self):
        """
        Checks what to do with `Callable`:

         1) if it is not callable, treat it as a result.
         2) if it's `Promise`, depend on it.
         3) if it's `threading.Event` or `threading.Condition`, wait for it and resolve.

        Else, pass on, wait for start.
        """
        func = self.Callable  # type: Promise

        if isinstance(func, Promise):
            def wait_and_resolve():
                """
                Waits for passed in `Promise` and resolves in the same way.
                """
                func.wait()
                if func.resolved is True:
                    return func.result
                else:
                    if func.exc_info is not None:
                        if PY3:
                            raise func.exception.with_traceback(func.exc_info[2])
                        raise func.exc_info[0], func.exc_info[1], func.exc_info[2]
                    else:
                        raise func.exception

            func.print_exception = False
            self.Callable = wait_and_resolve
            self()

        elif _is_waitable(func):
            def wait_event():
                """
                Waits for notifyable to be set.
                """
                func.wait()
                err = is_failed(func)
                if err is not None:
                    raise err

                return get_result(func)

            self.Callable = wait_event
            self()

        elif not callable(func):
            self.result = func
            self.started.set()
            self.finished.set()
            self.resolved = True

    @staticmethod
    def resolve(thing):
        """
        Creates a `Promise` resolved to ``thing``.

        :param thing: thing to resolve.
        :rtype: Promise
        """
        p = Promise()
        p.result = thing
        return p

    @staticmethod
    def reject(thing):
        """
        Creates a `Promise` rejected to ``thing``.

        :param thing: thing to reject.
        :rtype: Promise
        """
        p = Promise()
        p.exception = thing
        p.resolved = False
        return p

    @staticmethod
    def all(things):
        """
        Creates a `Promise` that waits for each one of ``things``, or rejects with the first failed one of them.

        :param list things: things to wait.
        :rtype: Promise
        """

        def all_resolver():
            """
            Internal, resolver for the new `Promise`.

            :return list: results
            """
            stop = threading.Event()
            stop.rejected = None
            stop.count = 0
            for i, thing in enumerate(things):
                if isinstance(thing, Promise):
                    stop.count += 1

                    def closure(i, thing):
                        """
                        Closure to save indexes.

                        :param i: index
                        :param thing: current `Promise`
                        :return:
                        """

                        def resolver(result):
                            things[i] = result
                            stop.set()
                            stop.count -= 1

                        def excepter(_, __):
                            stop.rejected = thing
                            stop.set()

                        thing.then(resolver, excepter)

                    closure(i, thing)

            while stop.count:
                stop.wait()
                if stop.rejected is not None:
                    if stop.rejected.exc_info is not None:
                        if PY3:
                            raise stop.rejected.exception.with_traceback(stop.rejected.exc_info[2])
                        raise stop.rejected.exc_info[0], stop.rejected.exc_info[1], stop.rejected.exc_info[2]
                    else:
                        raise stop.rejected.exception
                stop.clear()

            return things

        p = Promise(all_resolver)
        return p()

    @staticmethod
    def race(things):
        """
        Creates a `Promise` that waits to any of ``things`` and returns it's result.

        :param list things: things to wait.
        :rtype: Promise
        """

        def all_resolver():
            """
            Internal, resolver for the new `Promise`.

            :return: result
            """
            stop = threading.Event()
            stop.finished = None  # type: Promise
            for thing in things:
                if isinstance(thing, Promise):
                    def closure(thing):
                        def resolver(*_):
                            stop.set()
                            stop.finished = thing

                        thing.then(resolver, resolver)

                    closure(thing)
                else:
                    return thing

            stop.wait()
            if stop.finished.resolved is True:
                return stop.finished.result
            else:
                if stop.finished.exc_info is not None:
                    if PY3:
                        raise stop.finished.exception.with_traceback(stop.finished.exc_info[2])
                    raise stop.finished.exc_info[0], stop.finished.exc_info[1], stop.finished.exc_info[2]
                else:
                    raise stop.finished.exception

        p = Promise(all_resolver)
        return p()

    def __resolve_name(self):
        """
        Resolves the name of the Promise.
        """
        func = self.Callable
        if hasattr(func, 'func_globals') and hasattr(func, 'func_code'):
            self.name = "%s:%d:%s" % (func.func_globals["__name__"], func.func_code.co_firstlineno, func.__name__)
        else:
            self.name = 'Promise(%s)' % str(func)

    def __call__(self, *args, **kwargs):
        """
        Thread starter.

        Saves the state, the function arguments, the thread name and starts the thread.

        Variadic, reentrant.
        """
        if not self.started.is_set():
            self.started.set()
            current = threading.currentThread()
            self.parent = (current.getName(), current.ident)

            self.__args = args
            self.__kwargs = kwargs
            self.start()
        return self

    def wait(self, timeout=None):
        """
        Waits for the function to complete.

        :raises TimeoutError: when timeout reached.

        :param timeout: seconds, optional.
        :type timeout: int or None
        :return: Result of the function.
        """
        if not self.finished.is_set():
            self.finished.wait(timeout)
        if not self.finished.is_set():
            raise TimeoutError()
        else:
            return self.result

    def then(self, resolved=None, rejected=None, print_exception=logging.ERROR):
        """
        The promise result. This function creates a new Promise which waits for current one, and calls corresponding
        function:

        :param resolved: Is called when function ended up conveniently. Receives result as a parameter.
        :param rejected: Is called if function raises an exception, receives the exception.
        :param print_exception: Log level to output the exception, or None to mute it. See `logging`.
        :rtype: Promise
        """
        self.print_exception = None
        me = self

        def wait_and_resolve():
            """
            Waits for current promise and resolves it.
            """
            me.wait()
            if me.resolved is True:
                if callable(resolved):
                    return resolved(me.result)
                else:
                    return me.result
            else:
                if callable(rejected):
                    return rejected(me.exception, me.exc_info)
                else:
                    if me.exc_info is not None:
                        if PY3:
                            raise me.exception.with_traceback(me.exc_info[2])
                        raise me.exc_info[0], me.exc_info[1], me.exc_info[2]
                    else:
                        raise me.exception

        p = Promise(wait_and_resolve, print_exception=print_exception)
        return p()

    def catch(self, callback=None, print_exception=logging.ERROR):
        """
        Same as `then` ``(None, callback)``

        :param callback: Is called if function raises an exception, receives the exception.
        :param print_exception: Log level to output the exception, or None to mute it.
        :rtype: Promise
        """
        return self.then(rejected=callback, print_exception=print_exception)

    def run(self):
        """
        Thread entrance point.

        Runs the function and then the callback.
        """
        try:
            args = self.__args
            kwargs = self.__kwargs
            self.__args = None
            self.__kwargs = None

            self.result = self.Callable(*args, **kwargs)
            self.resolved = True
        except Exception as e:
            info = sys.exc_info()
            if self.print_exception is not None and self.print_exception is not False:
                log_exception(e, info, level=self.print_exception)
            self.exception = e
            self.exc_info = info
            self.resolved = False
        finally:
            self.finished.set()


def async(function=None, daemon=False, print_exception=logging.ERROR, no_promise=False):
    """
    Decorator around the functions for them to be asynchronous.

    Used as a plain decorator or along with named arguments.

    Usage:

    .. code-block:: python

        @async
        def f1():
            pass

        @async(daemon=True)
        def f2():
            pass

    :param function: The function to be decorated.
    :param Boolean daemon: Optional. Create the daemon thread, that will die when no other threads left.
    :param print_exception: Log level to log the exception, if any, or None to mute it. See `logging`.
    :param no_promise: will not return promise.
    :return: Wrapped function.
    """
    if function is None:
        def add_async_callback(func):
            """
            A second stage of a wrapper that is used if a wrapper is called with arguments.

            :param func: The function to be decorated.
            :return: Wrapped function.
            """
            return async(func, daemon, print_exception, no_promise)

        return add_async_callback
    else:
        @functools.wraps(function)
        def async_caller(*args, **kwargs):
            """
            An actual wrapper, that creates a thread.

            :return: Thread of the function.
            :rtype: Promise
            """
            promise = Promise(function,
                              daemon=daemon,
                              print_exception=print_exception)(*args, **kwargs)
            if not no_promise:
                return promise

        async_caller.async = True

        return async_caller
