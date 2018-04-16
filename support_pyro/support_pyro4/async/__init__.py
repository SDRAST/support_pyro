import logging
import functools

import six
import Pyro4
import gevent

from .async_proxy import AsyncProxy
from .event_emitter import EventEmitter, EventEmitterProxy

module_logger = logging.getLogger(__name__)

__all__ = ["CallbackProxy", "async_method", "async_callback", "AsyncProxy", "EventEmitter", "EventEmitterProxy"]

class CallbackProxy(object):
    """
    A container for callbacks. This class proves more useful than simply
    passing around dictionaries because it enforces a consistent syntax for
    handling callbacks. This is only used by the async_method decorator.


    Attributes:
        cb (callable): a callable that represents a client-side callback
        cb_updates (callable): a callable that represents a client-side callback
            This is only present for backwards compatibility.
        cb_handler (Pyro4.Proxy): The proxy from which we get _RemoteMethods
            that are the cb and cb_updates attributes.
    """
    def __init__(self, cb_info=None, socket_info=None, func_name=None):
        """
        Keyword Args:
            cb_info (dict): Callback info (None)
            socket_info (dict): Information about the flask_socketio socket (None)
            func_name (str): DEPRECATED.
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
                    if socket_info is not None:
                        module_logger.debug("CallbackProxy.__init__: socket_info is not None")
                        app = socket_info['app']
                        socketio = socket_info['socketio']
                        def f(cb_name):
                            def emit_f(*args, **kwargs):
                                with app.test_request_context("/"):
                                    # module_logger.debug("CallbackProxy.__init__:f.emit_f: calling socket.emit")
                                    socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
                                    # module_logger.debug("CallbackProxy.__init__:f.emit_f: socket.emit called")
                                # socketio.sleep(0)
                            return emit_f
                        setattr(self, key, f(cb))
                    else:
                        module_logger.debug("CallbackProxy.__init__: socket_info is None")
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
        self.long_running_method.cb(update_info)
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

    We have to make sure that our client has registered the `long_running_method_cb`
    method:

    ```python
    import threading

    import Pyro4

    class Handler(object):

        def __init__(self):
            self.daemon = Pyro4.Daemon()
            self.uri = self.daemon.register(self)
            self.daemon_thread = threading.Thread(target=self.daemon.requestLoop)

        def long_running_method_cb(self, res)
            print(res)

        def long_running_method_cb_updates(self, res)
            print(res)

    uri = "" # some valid Pyro4 URI refering to a server with long_running_method registered.

    handler = Handler()
    proxy = Pyro4.Proxy(uri)

    proxy.long_running_method(cb_info={"cb_handler":handler.uri,
                                        "cb":"long_running_method_cb",
                                        "cb_updates":"long_running_method_cb_updates"})

    # Alternatively, we can pass a Proxy object refering to the handler to
    # long_running_method:

    proxy.long_running_method(cb_info={"cb_handler":Pyro4.Proxy(handler.uri),
                                        "cb":"long_running_method_cb",
                                        "cb_updates":"long_running_method_cb_updates"})
    ```

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

    Args:
        func (function): Function or method we'd like to decorate
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        """
        Process cb_info dictionary, setting function attributes accordingly.
        The decorator assumes a cb_info dictionary with the following keys:
        cb_info:
            cb_handler (Pyro4.Daemon): The handler object
            cb (str): The name of the final callback
            cb_updates (str, optional): The name of the updates callback
        Args:
            args (list/tuple): passed to func
            kwargs (dict): kwargs dictionary containing "cb_info"
        Returns:
            result of decorated function.
        """
        name = func.__name__

        if name == "__init__": # We're decorating a class, namely a worker class
            this = self
        else:
            this = wrapper
        module_logger.debug("async.wrapper.{}: kwargs: {}".format(name, kwargs))
        cb_info = kwargs.pop("cb_info", None)

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

        self._called[func.__name__] = True
        res = func(self, *args, **kwargs)
        self._res[func.__name__] = res
        return res
    wrapper._asyncCallback = True
    return Pyro4.expose(wrapper)
