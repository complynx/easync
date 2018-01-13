EAsync -- easy async decorator and promises
===========================================

.. image:: https://travis-ci.org/complynx/easync.svg?branch=master
    :target: https://travis-ci.org/complynx/easync

@async
======

Decorator around the functions for them to be asynchronous.

Used as a simple decorator or along with named arguments. Preserves function's or method's docs, names and other stuff
using ``functools.wraps``.

When the wrapped function is called, it produces the Promise_ of itself.

Usage:

>>> from easync import async
>>> @async
>>> def f1():
>>>    # some heavy-weight code

>>> @async(daemon=True, print_exception=False)
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
:param print_exception: Log level to log the exception, if any, or None to mute it. See ``logging``.
:param no_promise: Will not return a thing, instead of returning Promise_, good for decorating, for example, Tornado
                   handlers.
:return: Wrapped function, Promise_ generator.


Promise
=======

This is a threading wrapper that performs asynchronous call of the provided function.
The behaviour is inspired by JavaScript Promises, but differs in several points.

First, the resolution is based upon the return of the function beneath.
On successful return, the result is stored in `Promise.result`_
On exception, exception is stored in `Promise.exception`_
More about how Promise_ resolves in `Resolving Promises`_.

You can add callbacks by using methods `Promise.then`_
or `Promise.catch`_
They will create a new `Promise`_
resolving in either the resolution of the previous one or the underlying callback.

If at the final stage no exception is processed or were generated new ones, they will be printed.

Basic usage:

>>> from easync import Promise
>>> promise = Promise(func)(...args)
>>> promise.wait()
<result>  # if any
>>> promise.result
<result>  # if any
>>> promise.exception
Exception  # if something went wrong
>>> promise.exc_info
Tuple (Exception.__class__, Exception, traceback)  # if any

Callbacks usage:

>>> def callback(result):
>>>     do_stuff(result)
>>> def error(exception, exc_info):
>>>     my_log(exception, exc_info=exc_info)
>>> def some_final(_):
>>>     cleanup()
>>> Promise(func)(...args).then(callback, error).then(some_final)
Promise(...)

.. _Promise.Callable:

Promise.Callable
    The to-be-runned function.

.. _Promise.result:

Promise.result
    This parameter holds the result the underlying function returned.

.. _Promise.exception:

Promise.exception
    This parameter holds the exception if the underlying function fails.

.. _Promise.exc_info:

Promise.exc_info
    This parameter holds the exception information tuple if the underlying function fails and the tuple was recovered.
    In case of `Promise.reject`_, it will be None.

.. _Promise.resolved:

Promise.resolved
    True if the function resolves. More about it in `Resolving Promises`_.

.. _Promise.started:

Promise.started
    ``threading.Event``, sets when thread is started.

.. _Promise.finished:

Promise.finished
    ``threading.Event``, sets when thread is finished, no matter where had it been resolved or not.

.. _Promise.print_exception:

Promise.print_exception
    Enables exception printout if caught. Uses logging to do so and has to be one of logging levels. ``False`` or
    ``None`` disable. Also automatically sets to False when a dependent Promise_ created through `Promise.then`_ or
    `Promise.catch`_.


Resolving Promises
------------------


Functions
^^^^^^^^^

If the Promise_ is constructed with a function, it will resolve in it's return or reject with the caught exception.

Other Promises
^^^^^^^^^^^^^^

Just resolves in the same way the other one is resolved. Printouts will be suppressed in the first one.

Events and Conditions
^^^^^^^^^^^^^^^^^^^^^

If Promise_ is based on ``threading.Event`` or ``threading.Condition``, it is resolved when the underlying Event or
Condition occurs. The type testing is duck-type for having the ``wait`` method, so anything using the interface of
waiting can be resolved, for example other Promises, or threads.

The resolving is based on testing `is_failed`_ on the object, and if that one returns, the Promise_ rejects. Otherwise,
the `get_result`_ is called to obtain the result. Both are duck-type thingeys.

Anything else
^^^^^^^^^^^^^

Resolves successfully with the result equals to the passed-in argument.

Promise.__init__
----------------

``__init__(function[, daemon=False, print_exception=logging.ERROR])``

The constructor creates a ``threading.Thread`` wrapping the ``function``.
To start it, call the resulting object as a function with it's arguments. (Explained in `Promise.__call__`_)

>>> promise = Promise(func, print_exception=None)
>>> promise()

:param function: Function, Event, Condition, or anything else to resolve.
:param daemon: Sets up daemon flag in the thread. May be set later. Optional.
:param print_exception: Sets up the final exception printing level. Pass ``False`` to suppress.

Promise.__call__
----------------

``__call__(*args, **kwargs)``

Starts the thread and passes the arguments of the function into it.
Returns self, for simple adding `Promise.then`_, `Promise.wait`_ or `Promise.catch`_.

Promise.wait
------------

``wait([timeout=None])``

Pauses the current thread to wait until the underlying promise resolves.

If ``timeout`` is set, raises ``easync.TimeoutError`` if it's reached.

Returns result of the underlying function if there's any.

Promise.then
------------

``then([resolved=None, rejected=None, print_exception=Promise.print_exception])``

This method sets callbacks for a Promise_.

**NOTE** this method suppresses the Promise_ default error handling by setting `Promise.print_exception`_ to ``False``.
You can then re-enable printouts manually, overriding the `Promise.print_exception`_ yourself.

**NOTE** calling this method twice on the same Promise_ object will result in duplicated exception printouts unless
changed.

The result is a new Promise_ which resolves in:

:callback exception:    If the called callback (either ``resolved`` or ``rejected``) failed or raised anything.
:reject:                If the underlying Promise_ rejected and no ``rejected`` callback was passed.
:callback return:       The result of the called callback.
:resolve:               The result of the underlying Promise_ if it resolves and no ``resolved`` callback was passed.

This is done to have this kind of behaviour:

>>> Promise(action)(...args).then(parse_result).then(parse_one_more_result).catch(any_exception).then(cleanup)

:function resolved(result):                 The positive callback for the Promise_. Has to accept one positional
                                            argument - the result.
:function rejected(exception, exc_info):    The negative callback for the Promise_. Has to accept two positional
                                            arguments - the caught exception and it's exc_info.
:print_exception:                           Passed into the corresponding argument of the newly created Promise_.
:return:                                    New Promise_.

Promise.catch
-------------

``catch([callback=None, print_exception=Promise.print_exception])``

The same as `Promise.then`_ (resolved=None, callback, print_exception).

Promise static methods
======================

Promise.resolve
---------------

``Promise.resolve(thing)``

Resolves ``thing``, regardless of what it is, to result.

:param thing: any
:return: resolved Promise_ with the `Promise.result`_ equals to ``thing``.

Promise.reject
--------------

``Promise.reject(thing)``

Rejects ``thing``, regardless of what it is.

**NOTE**, if this will be called, the `Promise.exc_info`_ will be set None.

:param thing: any
:return: rejected Promise_ with the `Promise.exception`_ equals to ``thing``.

Promise.all
-----------

``Promise.all(things)``

Resolves when *all* the items in the ``enumerate(things)`` are resolved.
Or rejects when *any* of the items is rejected.

:param things: ``list`` of things or anything to be ``enumerate``'d.
:result: ``list`` of results of all the Promises for each of the items.
:exception: first caught exception.

Promise.race
------------

``Promise.race(things)``

Resolves when *any* of the items in the ``enumerate(things)`` is resolved.
Or rejects when *any* of the items is rejected.

:param things: ``list`` of things or anything to be ``enumerate``'d.
:result: the result of the first resolved item.
:exception: first caught exception.

Other functions
===============

get_result
----------

``get_result(obj)``

Returns the first found attribute of ``result`` or ``success`` of the object obj, if any. Otherwise returns ``None``.

is_failed
---------

``is_failed(obj)``

Returns:

:found property: if one of ``error``, ``exception``, ``failure`` is found.
:True: if one of ``failed`` or ``is_failed`` is true.
:True: if ``success`` is present and is ``False``.
:None: Otherwise

