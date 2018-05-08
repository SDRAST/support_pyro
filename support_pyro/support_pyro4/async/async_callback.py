import logging
import functools
import inspect

import Pyro4

__all__ = ["async_callback"]

module_logger = logging.getLogger(__name__)

def async_callback(func):
    """
    Client side decorator for methods indicating that they are
    to be used as callbacks.

    This decorator adds two attributes to the method's object, if not
    already present: "_called" and "_res" dictionaries. The former
    contains a boolean indicating whether the method has been called,
    and the latter contains the result of the callback.

    In addition, the decorator adds a "_asyncCallback" attribute to the
    wrapped function.

    Returns:
        Pyro4.expose'd wrapper of func
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_called"):
            self._called = {func.__name__: False}
        if not hasattr(self, "_res"):
            self._res = {func.__name__:None}
        if not hasattr(self, "_calls"):
            self._calls = {func.__name__:0}

        res = func(self, *args, **kwargs)
        self._res[func.__name__] = res
        self._called[func.__name__] = True
        self._calls[func.__name__] += 1

        return res
    wrapper._asyncCallback = True
    return Pyro4.expose(wrapper)
