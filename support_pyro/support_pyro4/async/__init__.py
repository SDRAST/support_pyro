import logging
import functools

import six
import Pyro4

from .async_proxy import AsyncProxy
from .event_emitter import EventEmitter

module_logger = logging.getLogger(__name__)

__all__ = ["CallbackProxy", "async_method", "async_callback", "AsyncProxy", "EventEmitter"]

class CallbackProxy(object):
    """
    Creates an object that has two callable attributes:
    cb: A 'final' callback function -- a client side method that is meant
        to be called when a server side method is finished
    cb_updates: An 'update' callback function -- a client side method that is
        meant to be called when the server side method has new information for
        the client
    """
    def __init__(self, cb_info=None, socket_info=None, func_name=None):
        """
        Keyword Args:
            cb_info (dict): Callback info (None)
            socket_info (dict): Information about the flask_socketio socket (None)
        """
        if not cb_info:
            self.cb = lambda *args, **kwargs: None
            self.cb_updates = lambda *args, **kwargs: None
            self.cb_handler = None
        else:
            dummy = lambda *args, **kwargs: None
            self.cb_handler = cb_info.get('cb_handler', None)
            for key in ["cb", "cb_updates"]:
                cb = cb_info.get(key, None)
                if not cb:
                    setattr(self, key, dummy)
                if callable(cb):
                    setattr(self, key, cb)
                elif isinstance(cb, six.string_types):
                    if socket_info:
                        app = socket_info['app']
                        socketio = socket_info['socketio']
                        def f(cb_name):
                            def emit_f(*args, **kwargs):
                                with app.test_request_context("/"):
                                    socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
                            return emit_f
                        setattr(self, key, f(cb))
                    else:
                        if self.cb_handler is not None:
                            try:
                                setattr(self, key, getattr(self.cb_handler, cb))
                                setattr(self, key+"_name", cb)
                            except AttributeError as err:
                                setattr(self, key, dummy)
                        else:
                            raise RuntimeError("Need to provide a callback handler of type Pyro4.core.Proxy")


def async_method(func):
    """
    Decorator that declares that a method is to be called asynchronously.
    Methods that are decorated with this class use a common callback interface.
    Say you have a server side method, `long_running_method` decorated with
    `async_method`:

    ```python
    ...
    @async_method
    def long_running_method(self, *args, **kwargs):
        ...
        self.long_running_method.cb_updates(update_info)
        ...
        self.long_running_method.cb(final_info)
    ...
    ```

    Any method that is decorated with this decorator will have three new attributes:
    "cb", "cb_updates", and "cb_handler". This assumes no a priori information about
    the client to which we are connected.

    Now client side, we would call `long_running_method` as follows:

    ```python
    # Here handler is some Pyro4.Daemon that has some methods/objects registered to it.
    client.long_running_method(*args,cb_info={'cb_handler':handler,
                                        "cb":"long_running_method_cb",
                                        "cb_updates":"long_running_method_cb_updates"})
    ```

    This is no doubt a little verbose client side, but it helps to create a clear
    and consistent separation between client and server.

    Note that you can also decorate "__init__" functions, but the behavior is different.
    Instead of setting *function* attributes, we set *instance attributes*. This is mostly
    useful for worker threads:

    ```python
    class Worker(threading.Thread):

        @async_method
        def __init__(self,*args, **kwargs):
            threading.Thread.__init__(self)

        def run(self):
            ...
            self.cb_updates(update_info)
            ...
            self.cb(cb_info)
    ```

    I wouldn't recommend using this on large classes, because it clutters and confuses
    the attribute space.

    Args:
        func (function): Function or method we'd like to decorate
    """
    module_logger.debug("async_method: called")
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        """
        Process cb_info dictionary, setting function attributes accordingly.
        The decorator assumes a cb_info dictionary with the following keys:
        cb_info:
            cb_handler (Pyro4.Daemon): The handler object
            cb (str): The name of the final callback
            cb_updates (str, optional): The name of the updates callback
        """
        name = func.__name__

        if name == "__init__": # We're decorating a class, namely a worker class
            this = self
        else:
            this = wrapper
        module_logger.debug("async.wrapper.{}: kwargs: {}".format(name, kwargs))
        if 'cb_info' in kwargs:
            cb_info = kwargs.pop("cb_info")
        else:
            cb_info = None

        if 'socket_info' in kwargs:
            socket_info = kwargs['socket_info']
            kwargs.pop('socket_info')
        else:
            socket_info = None

        this.cb_info = cb_info
        this.socket_info = socket_info
        module_logger.debug("async.wrapper.{}: cb_info: {}".format(name, this.cb_info))
        module_logger.debug("async.wrapper.{}: socket_info: {}".format(name, this.socket_info))
        cur_handler = getattr(self, "cb_handler", None)
        if this.cb_info:
            if "cb_handler" not in this.cb_info:
                this.cb_info["cb_handler"] = cur_handler
        async_cb = CallbackProxy(cb_info=this.cb_info, socket_info=this.socket_info, func_name=name)
        this.cb = async_cb.cb
        this.cb_updates = async_cb.cb_updates
        this.cb_handler = async_cb.cb_handler
        try:
            this.cb_name = async_cb.cb_name
            this.cb_updates_name = async_cb.cb_updates_name
        except AttributeError:
            pass

        return func(self, *args, **kwargs)

    wrapper._pyroAsync = True
    if func.__name__ == "__init__":
        return wrapper
    else:
        return Pyro4.expose(Pyro4.oneway(wrapper))

def async_callback(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_called"):
            self._called = {fn.__name__: False}
        if not hasattr(self, "_res"):
            self._res = {fn.__name__:None}

        self._called[fn.__name__] = True
        res = fn(self, *args, **kwargs)
        self._res[fn.__name__] = res
        return res
    wrapper._asyncCallback = True
    return Pyro4.expose(wrapper)
