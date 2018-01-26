from .supports import Promise2and3


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

    @staticmethod
    def _raise(exception, exc_info=None):
        """
        Raises the passed exception.
        As this is python version specific, it is to be implemented according to the specified version's syntax.

        :param Exception exception:
        :param () exc_info:
        :raise: exception
        """
        if exc_info is not None:
            raise exc_info[0], exc_info[1], exc_info[2]
        else:
            raise exception
