import threading
import logging
import sys
import traceback

logger = logging.getLogger('easync')


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
        msg = '{}: {}'.format(type(exception).__name__, exception)
        msg += '\nTraceback: (latest call first)' + tb_str + 'Thread: {}({:d})'.format(thread.getName(), thread.ident)

        logger.handle(logger.makeRecord(logger.name, level, tb[0][0], tb[0][1], msg, (), None, tb[0][2]))
    except Exception as e:
        logger.error("Could not make an exception trace for exception: {}\nCaught exception: {}".format(exception, e),
                     exc_info=sys.exc_info())


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


def is_waitable(obj):
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


class PromiseTimeoutError(RuntimeError):
    """
    Raised during wait, if timeout reached.
    """
    pass


class Promise2and3(threading.Thread):
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
        super(Promise2and3, self).__init__()
        self.print_exception = print_exception
        self.Callable = function
        self.daemon = daemon
        self.__resolve_name()
        self.started = threading.Event()
        self.finished = threading.Event()

        self._check_callable()

    def _check_callable(self):
        """
        Checks what to do with `Callable`:

         1) if it is not callable, treat it as a result.
         2) if it's `Promise`, depend on it.
         3) if it's `threading.Event` or `threading.Condition`, wait for it and resolve.

        Else, pass on, wait for start.
        """
        func = self.Callable

        if isinstance(func, Promise2and3):
            def wait_and_resolve():
                """
                Waits for passed in `Promise` and resolves in the same way.
                """
                func.wait()
                if func.resolved is True:
                    return func.result
                else:
                    self._raise(func.exception, func.exc_info)

            func.print_exception = False
            self.Callable = wait_and_resolve
            self()

        elif is_waitable(func):
            def wait_event():
                """
                Waits for notifyable to be set.
                """
                func.wait()
                err = is_failed(func)
                if err is not None:
                    self._raise(err)

                return get_result(func)

            self.Callable = wait_event
            self()

        elif not callable(func):
            self.result = func
            self.started.set()
            self.finished.set()
            self.resolved = True

    @staticmethod
    def _raise(exception, exc_info=None):
        """
        Raises the passed exception.
        As this is python version specific, it is to be implemented according to the specified version.

        :param Exception exception:
        :param () exc_info:
        :raise: exception
        """
        raise NotImplementedError

    @classmethod
    def resolve(cls, thing):
        """
        Creates a `Promise` resolved to ``thing``.

        :param thing: thing to resolve.
        :rtype: Promise
        """
        p = cls()
        p.result = thing
        return p

    @classmethod
    def reject(cls, thing):
        """
        Creates a `Promise` rejected to ``thing``.

        :param thing: thing to reject.
        :rtype: Promise
        """
        p = cls()
        p.exception = thing
        p.resolved = False
        return p

    @classmethod
    def all(cls, things):
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
                if isinstance(thing, Promise2and3):
                    stop.count += 1

                    def closure(i, thing):
                        """
                        Closure to save indexes.

                        :param i: index
                        :param thing: current `Promise`
                        :return:
                        """

                        def excepter(_, __):
                            stop.rejected = thing
                            stop.set()

                        def resolver(result):
                            needs_stop = True
                            if isinstance(result, Promise2and3):
                                needs_stop = False
                                result.then(resolver, excepter)
                            things[i] = result
                            if needs_stop:
                                stop.set()
                                stop.count -= 1

                        thing.then(resolver, excepter)

                    closure(i, thing)

            while stop.count:
                stop.wait()
                if stop.rejected is not None:
                    cls._raise(stop.rejected.exception, stop.rejected.exc_info)
                stop.clear()

            return things

        p = cls(all_resolver)
        return p()

    @classmethod
    def race(cls, things):
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
            stop.finished = None  # type: cls
            _things = list(things)
            for i, thing in enumerate(_things):
                if isinstance(thing, Promise2and3):
                    def closure(i, thing):
                        def resolver(*_):
                            needs_stop = True
                            if isinstance(_things[i].result, Promise2and3):
                                needs_stop = False
                                t = _things[i] = _things[i].result
                                t.then(resolver, resolver)
                            if needs_stop:
                                stop.set()
                                stop.finished = thing

                        thing.then(resolver, resolver)

                    closure(i, thing)
                else:
                    return thing

            stop.wait()
            if stop.finished.resolved is True:
                return stop.finished.result
            else:
                cls._raise(stop.finished.exception, stop.finished.exc_info)

        p = cls(all_resolver)
        return p()

    def __resolve_name(self):
        """
        Resolves the name of the Promise.
        """
        func = self.Callable
        if hasattr(func, 'func_globals') and hasattr(func, 'func_code'):
            self.name = "{global_name}:{line:d}:{name}"\
                .format(line=func.func_code.co_firstlineno,
                        name=func.__name__,
                        global_name=func.func_globals['__name__'])
        else:
            self.name = 'Promise({})'.format(repr(func))

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
            raise PromiseTimeoutError()
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
                    self._raise(me.exception, me.exc_info)

        p = self.__class__(wait_and_resolve, print_exception=print_exception)
        return p()

    def catch(self, callback=None, print_exception=logging.ERROR):
        """
        Same as `then` ``(None, callback)``

        :param callback: Is called if function raises an exception, receives the exception.
        :param print_exception: Log level to output the exception, or None to mute it.
        :rtype: Promise
        """
        return self.then(rejected=callback, print_exception=print_exception)

    def resolve_subsequent(self, result):
        """
        Resolves all the promises returned by the function, if any.
        Because the result is not a promise!
        :param result:
        :return:
        """
        while isinstance(result, Promise2and3):
            result.print_exception = None
            result.wait()
            if result.resolved is False:
                self._raise(result.exception, result.exc_info)
            result = result.result

        return result

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

            res = self.Callable(*args, **kwargs)

            self.result = self.resolve_subsequent(res)
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
