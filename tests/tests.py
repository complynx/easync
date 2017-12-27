# the inclusion of the tests module is not meant to offer best practices for
# testing in general, but rather to support the `find_packages` example in
# setup.py that excludes installing the "tests" package
import easync
import threading
import logging
import inspect

logging.basicConfig(level=logging.DEBUG)

pause_event = threading.Event()
pause_event.set()
to_be_true = threading.Event()


class FakeFail(Exception):
    pass


@easync.async
def to_fail():
    pause_event.wait()
    raise FakeFail("Failee")


@easync.async
def set_true():
    """
    this is comment
    """
    pause_event.wait()
    to_be_true.set()
    return 5


@easync.async(daemon=True)
def set_true_twostage():
    pause_event.wait()
    to_be_true.set()
    return 5


class Stub(object):
    @easync.async
    def set_true(self):
        """
        this is comment
        """
        pause_event.wait()
        to_be_true.set()
        return 5


def test_async():
    to_be_true.clear()
    pause_event.clear()
    set_true()
    pause_event.set()
    assert to_be_true.wait(1)


def test_async_method():
    to_be_true.clear()
    pause_event.clear()
    o = Stub()
    o.set_true()
    pause_event.set()
    assert to_be_true.wait(1)


to_be_true2 = threading.Event()


def result_asserter(x):
    if x == 5:
        to_be_true2.set()
        return True
    return False


def failure_asserter(e):
    if isinstance(e, FakeFail):
        to_be_true2.set()
        return True
    return False


def test_promise():
    to_be_true.clear()
    to_be_true2.clear()
    pause_event.clear()
    p = set_true()

    p.then(result_asserter)

    pause_event.set()
    assert to_be_true.wait(1)
    assert to_be_true2.wait(1)


def test_failure():
    to_be_true.clear()
    to_be_true2.clear()
    pause_event.clear()
    p = to_fail()

    p.catch(failure_asserter)

    pause_event.set()
    assert to_be_true2.wait(1)


def test_async_twostage():
    to_be_true.clear()
    pause_event.clear()
    set_true_twostage()
    pause_event.set()
    assert to_be_true.wait(1)


def test_promise_notifyable():
    to_be_true.clear()
    to_be_true2.clear()
    pause_event.clear()

    p = easync.Promise(to_be_true)

    assert p.started.wait(1)
    assert not p.resolved
    assert not p.finished.is_set()
    to_be_true.set()
    p.wait(1)
    assert p.finished.is_set()
    assert p.resolved


def test_promise_simple():
    to_be_true2.clear()
    pause_event.clear()

    p = easync.Promise(1)

    assert p.started.wait(1)
    p.wait(1)
    assert p.finished.is_set()
    assert p.resolved
    assert p.result == 1


def test_promise_resolve():
    to_be_true2.clear()
    pause_event.clear()

    p = easync.Promise.resolve(1)

    assert p.started.wait(1)
    p.wait(1)
    assert p.finished.is_set()
    assert p.resolved
    assert p.result == 1


def test_promise_reject():
    to_be_true2.clear()
    pause_event.clear()

    p = easync.Promise.reject(1)

    assert p.started.wait(1)
    p.wait(1)
    assert p.finished.is_set()
    assert not p.resolved
    assert p.exception == 1


def test_promise_all():
    to_be_true.clear()

    p = easync.Promise.all([1, to_be_true])

    assert p.started.wait(1)
    to_be_true.set()
    p.wait(1)
    assert p.finished.is_set()
    assert p.resolved
    assert p.result[0] == 1
    assert p.result[1] == to_be_true


def test_promise_race():
    to_be_true.clear()

    p = easync.Promise.race([1, to_be_true])

    assert p.started.wait(1)
    to_be_true.set()
    p.wait(1)
    assert p.finished.is_set()
    assert p.resolved
    assert p.result == 1


def test_async_functools():
    assert "this is comment" in set_true.__doc__
    assert "set_true" in set_true.__name__
    assert set_true.async
    assert callable(set_true)
    assert not inspect.ismethod(set_true)
    assert inspect.isfunction(set_true)


def test_async_method_functools():
    o = Stub()
    assert "this is comment" in o.set_true.__doc__
    assert "set_true" in o.set_true.__name__
    assert o.set_true.async
    assert inspect.ismethod(o.set_true)
    assert not inspect.isfunction(o.set_true)
