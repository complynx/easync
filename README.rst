EAsync -- easy async decorator and promises
===========================================

.. image:: https://travis-ci.org/complynx/easync.svg?branch=master
    :target: https://travis-ci.org/complynx/easync

@async
======

Decorator around the functions for them to be asynchronous.

Used as a plain decorator or along with named arguments. Preserves function's or method's docs, names and other stuff.
When wrapped function is called, it produces the `Promise`.

Usage:

>>> from easync import async
>>> @async
>>> def f1():
>>>    # some heavy-weight code

>>> @async(daemon=True, print_exception=None)
>>> def f2():
>>>     # some faulty daemon we don't really care about

>>> @async(print_exception=logging.WARNING)
>>> def f3():
>>>     # setting another logging level

>>> f1().wait()
<result>
>>> f2()  # started daemon
easync.Promise(...)
>>> f3().then(callback, error)  # notice, here the print_exception is suppressed (see Promise doc for more)
easync.Promise(...)

:param function: The function to be decorated.
:param Boolean daemon: Optional. Create the daemon thread, that will die when no other threads left.
:param print_exception: Log level to log the exception, if any, or None to mute it. See `logging`.
:return: Wrapped function, `Promise` generator.


Promise
=======


This is a threading wrapper that performs asynchronous call of the provided function.
The behaviour is inspired by JavaScript Promises, but differs in several points.

First, the resolution is based upon the return of the function beneath.
On successful return, the result is stored in `Promise.result`
On exception, exception is stored in `Promise.exception`

You can add callbacks by using methods `Promise.then()` or `Promise.catch()`.
They will create a new `Promise` resolving in either the resolution of the previous one or the underlying callback.

If at the final stage no exception is processed or were generated new ones, they will be printed.
*NOTE:* if two promises are based on the resolution of the _same_ promise, both will print.

Basic usage:

>>> from easync import Promise
>>> promise = Promise(func)(...args)
>>> promise.wait()
<result>  # if any
>>> promise.result
<result>  # if any
>>> promise.exception
Exception  # if something went wrong

Callbacks usage:

>>> def callback(result):
>>>     do_stuff(result)
>>> def error(exception):
>>>     my_log(exception)
>>> def some_final(_):
>>>     cleanup()
>>> Promise(func)(...args).then(callback, error).then(some_final)
Promise(...)

Promise.__init__
----------------

`Promise.__init__(function[, daemon=False, print_exception=logging.ERROR])`

The constructor creates a `threading.Thread` wrapping the `function`.
:param function: Function to resolve.
:param daemon: Sets up daemon flag in the thread. May be set later. Optional.
:param print_exception: Sets up the final exception printing level. Pass `None` to suppress.
