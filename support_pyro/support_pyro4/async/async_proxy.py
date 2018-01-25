import time
import uuid
import logging
import functools
import threading
import inspect

import Pyro4

pyro4_version_info = Pyro4.__version__.split(".")

module_logger = logging.getLogger(__name__)
module_logger.debug("from {}".format(__name__))

class AsyncProxy(Pyro4.core.Proxy):
    """
    Proxy that has a Pyro4 Daemon attached to it that registers methods.
    """
    __asyncAttributes = frozenset(
        ["_daemon","_daemon_thread","_asyncHandlers"]
    )

    def __init__(self, uri, daemon_details=None):

        if int(pyro4_version_info[1]) >= 70:
            Pyro4.core.Proxy.__init__(self, uri, daemon_details=daemon_details)
        else:
            Pyro4.core.Proxy.__init__(self, uri)

        self._asyncHandlers = {}

        if daemon_details is None:
            self._daemon = Pyro4.Daemon()
        else:
            if "daemon" in daemon_details:
                self._daemon = daemon_details["daemon"]
            else:
                host = daemon_details.get("host", None)
                port = daemon_details.get("port",0)
                self._daemon = Pyro4.Daemon(host=host, port=port)

        # self.register_handlers_with_daemon()
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
            if isinstance(callback,str):
                # attempt to find the callback in the global context
                callback_obj = globals()[callback]
                method_name = callback
            elif inspect.ismethod(callback):
                callback_obj = callback.im_self
                method_name = callback.__name__
            elif inspect.isfunction(callback):
                callback_obj = callback
                method_name = callback.__name__

            module_logger.debug("_pyroInvoke: calling register")
            obj, _ = self.register(callback_obj)[0]
            self.register_handlers_with_daemon()
            callback_dict["cb_handler"] = obj
            callback_dict["cb"] = method_name
            kwargs["cb_info"] = callback_dict

        module_logger.debug("_pyroInvoke: calling super, kwargs: {}".format(kwargs))
        resp = super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)
        module_logger.debug("_pyroInvoke: super called. resp: {}".format(resp))
        return resp

    def shutdown(self):
        self._daemon.shutdown()

    def register_handlers_with_daemon(self):
        module_logger.debug("register_handlers_with_daemon: self._daemon.objectsById (before): {}".format(list(self._daemon.objectsById.keys())))
        module_logger.debug("register_handlers_with_daemon: self._asyncHandlers: {}".format(list(self._asyncHandlers.keys())))
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]["object"]
            if objectId not in self._daemon.objectsById and not hasattr(obj, "_pyroId"):
                module_logger.debug(
                    "register_handlers_with_daemon: Registering object {} with objectId {}...".format(
                        obj.__class__.__name__, objectId[4:10]
                    )
                )
                uri = self._daemon.register(obj, objectId=objectId)
                self._asyncHandlers[objectId]["uri"] = uri
        module_logger.debug("register_handlers_with_daemon: self._daemon.objectsById (after): {}".format(list(self._daemon.objectsById.keys())))

    def register(self, *fn_or_objs):
        """
        Register a function (not a method) with the AsyncProxy.
        Args:
            fn_or_objs (list/callable): a list of functions or objects, or
                a single function or object. The function will get wrapped up
                in an exposed class, and the object will be registered as is.
        Returns:
            list: A list of [obj, objectId]'s.
        """
        module_logger.debug("register: called")
        return_vals = []
        for fn_or_obj in fn_or_objs:
            objectId = "obj_" + uuid.uuid4().hex # this is the same signature as Pyro4.core.Daemon
            module_logger.debug("register: creating objectId {}... for obj {}".format(objectId[4:11], fn_or_obj))
            if inspect.isfunction(fn_or_obj):
                handler_class = AsyncProxy.create_handler_class(fn_or_obj)
                handler_obj = handler_class()
            else:
                handler_obj = fn_or_obj
            name = handler_obj.__class__.__name__
            existing_obj_details = self.lookup(name)
            if existing_obj_details is None:
                self._asyncHandlers[objectId] = {"object": handler_obj}
                return_vals.append([handler_obj, objectId])
            else:
                module_logger.debug("register: object with name {} already exists".format(name))
                return_vals.append(existing_obj_details)
                # raise RuntimeError("Function or object with name {} already registered".format(name))
        return return_vals

    def lookup(self, fn_or_obj):
        """
        Given some function name, look it up in self._asyncHandlers, and
        return the object to which it refers.
        Args:
            fn_or_obj (str/function/object): The name of a function, the
                function itself, or an object.
        Returns:
            object, objectId, or None
        """
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]["object"]
            if isinstance(fn_or_obj, str):
                if obj.__class__.__name__ == fn_or_obj:
                    return obj, objectId
            elif inspect.isfunction(fn_or_obj):
                if obj.__class__.__name__ == fn_or_obj.__name__:
                    return obj, objectId
            else:
                if obj.__class__ is fn_or_obj.__class__:
                    return obj, objectId

    def unregister(self, fn_or_obj):
        """
        Remove an object from self._asyncHandlers and the _daemon attribute
        Args:
            fn_or_obj (str/function/object): The name of a function, the
                function itself, or an object.
        """
        obj_info = self.lookup(fn_or_obj)
        if obj_info is None:
            error_msg = "Couldn't find function or object {}".format(fn_or_obj)
            module_logger.error(error_msg)
            raise RuntimeError(error_msg)
        else:
            obj, objectId = obj_info
            del self._asyncHandlers[objectId]
            self._daemon.unregister(objectId)

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
