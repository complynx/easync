import threading
import logging
from .supports import (Promise2and3, is_waitable, is_failed, get_result)


class Promise(Promise2and3):
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

    def _check_callable(self):
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
                        raise func.exc_info[0], func.exc_info[1], func.exc_info[2]
                    else:
                        raise func.exception

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
                    raise stop.finished.exc_info[0], stop.finished.exc_info[1], stop.finished.exc_info[2]
                else:
                    raise stop.finished.exception

        p = Promise(all_resolver)
        return p()

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
                        raise me.exc_info[0], me.exc_info[1], me.exc_info[2]
                    else:
                        raise me.exception

        p = Promise(wait_and_resolve, print_exception=print_exception)
        return p()
