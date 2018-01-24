import uuid
import logging
import functools
import threading
import inspect

import Pyro4

module_logger = logging.getLogger(__name__)

class AsyncProxy(Pyro4.core.Proxy):
    """
    Proxy that has a Pyro4 Daemon attached to it that registers methods.
    """
    _asyncHandlers = {}
    __asyncAttributes = frozenset(
        ["_daemon","_daemon_thread","_asyncHandlers"]
    )

    def __init__(self, uri, daemon_details=None):

        Pyro4.core.Proxy.__init__(self, uri)

        if daemon_details is None:
            self._daemon = Pyro4.Daemon()
            self.register_handlers_with_daemon()
        else:
            if "daemon" in daemon_details:
                self._daemon = daemon_details["daemon"]
            else:
                host = daemon_details.get("host", None)
                port = daemon_details.get("port",0)
                self._daemon = Pyro4.Daemon(host=host, port=port)
        self._daemon_thread = threading.Thread(target=self._daemon.requestLoop)
        self._daemon_thread.daemon = True
        self._daemon_thread.start()

    def __getattr__(self, name):
        if name in AsyncProxy.__asyncAttributes:
            return super(Pyro4.core.Proxy, self).__getattribute__(name)
        return Pyro4.core.Proxy.__getattr__(self,name)

    def __setattr__(self, name, value):
        if name in AsyncProxy.__asyncAttributes:
            return object.__setattr__(self,name,value)
        return Pyro4.core.Proxy.__setattr__(self, name, value)

    def _pyroInvoke(self, methodname, vargs, kwargs, flags=0, objectId=None):
        """
        Override the Pyro4.Proxy _pyroInvoke method. This will modify the
        kwargs dictionary to automatically include a reference to the
        self._asyncHandler attribute.
        """
        module_logger.debug("_pyroInvoke: Called. methodname: {}, vargs: {}, kwargs: {}".format(methodname, vargs, kwargs))
        callback = None
        for key in ["callback", "cb_info", "cb"]:
            if key in kwargs:
                callback = kwargs.pop(key)
                break

        if callback is not None:
            callback_dict = {}
            if inspect.isfunction(callback):
                method_name = callback.__name__
                handler, handler_id = self.lookup_function(method_name)
            elif inspect.ismethod(callback):
                method_name = callback.__name__
                handler = callback.im_self
            elif isinstance(callback, str):
                method_name = callback
                handler, handler_id = self.lookup_function(method_name)
            elif isinstance(callback, dict):
                method_name = callback["callback"]
                handler = callback["handler"]

            callback_dict["cb_handler"] = handler
            callback_dict["cb"] = method_name
            kwargs["cb_info"] = callback_dict

        return super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)

    def shutdown(self):
        self._daemon.shutdown()

    def register_handlers_with_daemon(self):
        module_logger.debug("register_handlers_with_daemon: self._daemon.objectsById: {}".format(self._daemon.objectsById))
        module_logger.debug("register_handlers_with_daemon: self._asyncHandlers: {}".format(self._asyncHandlers))
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]
            if objectId not in self._daemon.objectsById and not hasattr(obj, "_pyroId"):
                module_logger.debug(
                    "register_handlers_with_daemon: Registering object {} with objectId {}".format(
                        obj, objectId
                    )
                )
                self._daemon.register(obj, objectId=objectId)

    def register(self, fn_or_obj):
        AsyncProxy.register(AsyncProxy, fn_or_obj)
        self.register_handlers_with_daemon()

    @classmethod
    def register(cls, fn_or_obj):
        """
        Register a function (not a method) with the AsyncProxy.
        Args:
            fn (callback): A function that doesn't take self as it's first
                parameter
        Returns:
            None
        """
        objectId = "obj_" + uuid.uuid4().hex # this is the same signature as Pyro4.core.Daemon
        module_logger.debug("Creating objectId {}... for obj {}".format(objectId[4:11], fn_or_obj))
        if inspect.isfunction(fn_or_obj):
            handler_class = AsyncProxy.create_handler_class(fn_or_obj)
            handler_obj = handler_class()
        else:
            handler_obj = fn_or_obj
        name = handler_obj.__class__.__name__
        if cls.lookup_function(name) is None:
            cls._asyncHandlers[objectId] = handler_obj
        else:
            raise RuntimeError("Function or object with name {} already registered".format(name))

    def lookup_function(self, fn_name):
        return AsyncProxy.lookup_function(AsyncProxy, fn_name)

    @classmethod
    def lookup_function(cls, fn_or_obj):
        """
        Given some function name, look it up in self._asyncHandlers, and
        return the object to which it refers.
        Args:
            fn_name (str):
        """
        for objectId in cls._asyncHandlers:
            obj = cls._asyncHandlers[objectId]
            if isinstance(fn_or_obj, str):
                if obj.__class__.__name__ == fn_or_obj:
                    return obj, objectId
            elif inspect.isfunction(fn_or_obj):
                if obj.__class__.__name__ == fn_or_obj.__name__:
                    return obj, objectId
            else:
                if obj.__class__ is fn_or_obj.__class__:
                    return obj, objectId

    @classmethod
    def unregister(cls, fn_or_obj):
        pass

    @staticmethod
    def create_handler_class(fn):
        """
        From a non instance method function, create a wrapper class
        Args:
            fn (callable): A function that will get exposed and wrapped in a class.
        """
        assert inspect.isfunction(fn), "{} should be of type function, not {}".format(fn, type(fn))
        module_logger.debug("AsyncProxy.create_handler_class: Creating handler class for function {}".format(fn))
        @functools.wraps(fn)
        def fn_wrapper(self, *args, **kwargs):
            return fn(*args, **kwargs)

        exposed_wrapper = Pyro4.expose(fn_wrapper)

        class Handler(object):
            pass

        setattr(Handler, fn.__name__, exposed_wrapper)
        Handler.__name__ = fn.__name__ # not sure this is the best solution
        return Handler
