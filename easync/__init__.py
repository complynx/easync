import functools
import sys
import logging
from .supports import (logger,  # NOQA: F401 -- we are importing it for the sake of others
                       log_exception,
                       PromiseTimeoutError,
                       is_waitable,
                       is_failed,
                       get_result)

if sys.version_info >= (3, 0):
    from .promise3 import (Promise)
else:
    from .promise2 import (Promise)


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
