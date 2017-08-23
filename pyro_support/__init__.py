__version__ = "1.2.0"
from flask_socketio import send, emit

from .pyro4_server import *
from .pyro4_client import *
from .configuration import config

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

        if 'cb_info' in kwargs:
            cb_info = kwargs['cb_info']
            kwargs.pop('cb_info')
        else:
            cb_info = None

        if 'socket_info' in kwargs:
            socket_info = kwargs['socket_info']
            kwargs.pop('socket_info')
        else:
            socket_info = None

        this.cb_info = cb_info
        this.socket_info = socket_info
        if not cb_info:
            this.cb = lambda *args, **kwargs: None
            this.cb_updates = lambda *args, **kwargs: None
            this.cb_handler = None
        else:
            cb = cb_info.get('cb', name+"_cb")
            this.cb_name = cb
            cb_updates = cb_info.get('cb_updates', name+"_cb_updates")
            this.cb_updates_name = cb_updates
            if not socket_info:
                cur_handler = getattr(self, "cb_handler", None)
                this.cb_handler = cb_info.get('cb_handler', cur_handler)
                try:
                    this.cb = getattr(this.cb_handler, cb)
                except AttributeError:
                    this.cb = lambda *args, **kwargs: None
                try:
                    this.cb_updates = getattr(this.cb_handler, cb_updates)
                except AttributeError:
                    this.cb_updates = lambda *args, **kwargs: None
            else:
                app = socket_info['app']
                socketio = socket_info['socketio']
                def f(cb_name):
                    def emit_f(*args, **kwargs):
                        with app.test_request_context("/"):
                            socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
                    return emit_f

                this.cb_handler = None
                this.cb = f(cb)
                this.cb_updates = f(cb_updates)

        return func(self, *args, **kwargs)
    wrapper._async_method = True
    return wrapper
