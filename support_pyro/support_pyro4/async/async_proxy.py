import time
import uuid
import logging
import functools
import threading
import inspect

import Pyro4

__all__ = ["AsyncProxy"]

pyro4_version_info = Pyro4.__version__.split(".")

module_logger = logging.getLogger(__name__)
module_logger.debug("from {}".format(__name__))

class AsyncProxy(Pyro4.core.Proxy):
    """
    Proxy that has a Pyro4 Daemon attached to it that registers methods.
    This is for passing callbacks to servers, such that the server can call
    client-side functions. This will register functions/methods on the fly.

    Say we have some server implemented as follows:

    ```python
    # async_server.py
    from support.pyro import async

    class AsyncServer(object):

        @async.async_method
        def async_method(self, *args):
            self.async_method.cb(args) # bounce back whatever is sent

    async_server = AsyncServer()
    async_server.launch_server(ns=False,objectId="AsyncServer",objectPort=9092)
    ```

    We could access this server as follows:

    ```python
    # async_client.py

    def handler(res):
        print("Got {} from server!".format(res))

    async_client = AsyncProxy("PYRO:AsyncServer@localhost:9092")
    async_client.async_method(5,callback=handler)
    while True:
        pass
    ```
    Note that the last bit is necessary if running inside a script, otherwise
    the client program will exit before the handler function can be called.

    This is not meant to be subclassed directly. Instead, if you'd like to
    access proxy methods/properties in a "Client" class, do so as follows:

    class Client(object):
        def __init__(self, uri):
            self.proxy = AsyncProxy(uri)
        def __getattr__(self, attr):
            return getattr(self.proxy, attr)

    Attributes:
        __asyncAttributes (frozenset): List of protected attributes.
        _asyncHandlers (dict): dictionary of functions/methods that are
            registered with the daemon.
        _daemon (Pyro4.Daemon): Daemon instance, used to register functions/methods
            as callbacks
        _daemon_thread (threading.Thread): thread in which _daemon's requestLoop
            is running.
    """
    __asyncAttributes = frozenset(
        ["_daemon","_daemon_thread","_asyncHandlers"]
    )
    def __init__(self, uri, daemon_details=None):
        """
        Args:
            uri (str/Pyro4.URI): passed to Pyro4.core.Proxy
            daemon_details (dict): Register the AsyncProxy on some prexisting
                Daemon.
        """
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
        """Make sure that we can access the custom __asyncAttributes"""
        if name in AsyncProxy.__asyncAttributes:
            return super(Pyro4.core.Proxy, self).__getattribute__(name)
        return Pyro4.core.Proxy.__getattr__(self,name)

    def __setattr__(self, name, value):
        """Make sure that we can access the custom __asyncAttributes"""
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
        if kwargs is not None:
            callback = None
            for key in ["callback", "cb_info", "cb"]:
                if key in kwargs:
                    callback = kwargs.pop(key)
                    break

            if callback is not None:
                callback_dict = {}

                res = self.lookup_function_or_method(callback)
                callback_obj = res["obj"]
                method_name = res["method"]

                module_logger.debug("_pyroInvoke: calling register")
                obj, _ = self.register(callback_obj)[0]
                self.register_handlers_with_daemon()
                callback_dict["cb_handler"] = obj
                callback_dict["cb"] = method_name
                kwargs["cb_info"] = callback_dict

        module_logger.debug("_pyroInvoke: calling super, methodname: {}, vargs: {}, kwargs: {}".format(
            methodname, vargs, kwargs
        ))
        resp = super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)
        module_logger.debug("_pyroInvoke: super called. resp: {}".format(resp))
        return resp

    def shutdown(self):
        """proxy for the daemon shutdown method."""
        self._daemon.shutdown()

    def register_handlers_with_daemon(self):
        """Register all the objects in _asyncHandlers with the _daemon attribute"""
        module_logger.debug("register_handlers_with_daemon: self._daemon.objectsById (before): {}".format(list(self._daemon.objectsById.keys())))
        module_logger.debug("register_handlers_with_daemon: self._asyncHandlers: {}".format(list(self._asyncHandlers.keys())))
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]["object"]
            if objectId not in self._daemon.objectsById and not hasattr(obj, "_pyroId"):
                module_logger.debug(
                    "register_handlers_with_daemon: Registering object {} with objectId {}...".format(
                        obj.__class__.__name__, objectId[4:11]
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
            if not hasattr(handler_obj, "_objectHandlerId"):
                handler_obj._objectHandlerId = objectId

            if objectId not in self._asyncHandlers:
                self._asyncHandlers[objectId] = {"object": handler_obj}

            return_vals.append([handler_obj, objectId])
            # existing_obj_details = self.lookup(handler_obj)
            # module_logger.debug("register: existing_obj_details: {}".format(existing_obj_details))
            # if len(existing_obj_details) == 0:
            #     module_logger.debug("register: no object with objectId {} exists".format(objectId[4:11]))
            #     self._asyncHandlers[objectId] = {"object": handler_obj}
            #     return_vals.append([handler_obj, objectId])
            # elif len(existing_obj_details) == 1:
            #     module_logger.debug("register: object with objectId {} found".format(objectId[4:11]))
            #     return_vals.append(existing_obj_details[0])
            # else:
            #     module_logger.debug("register: multiple objects found")
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
        module_logger.debug("lookup: type(fn_or_obj): {}".format(type(fn_or_obj)))
        module_logger.debug("lookup: hasattr(fn_or_obj, '_objectHandlerId'): {}".format(hasattr(fn_or_obj, '_objectHandlerId')))
        result = []
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]["object"]
            if hasattr(fn_or_obj, "_objectHandlerId"):
                if fn_or_obj._objectHandlerId == objectId:
                    result.append([obj, objectId])
            elif isinstance(fn_or_obj, str):
                if obj.__class__.__name__ == fn_or_obj:
                    result.append([obj, objectId])
            elif inspect.isfunction(fn_or_obj): # we can only lookup by name
                if obj.__class__.__name__ == fn_or_obj.__name__:
                    result.append([obj, objectId])
            else:
                if obj.__class__ is fn_or_obj.__class__:
                    result.append([obj, objectId])
        return result

    def lookup_function_or_method(self, callback):
        """
        Given some string (corresponding to a function in the global scope),
        a function object, or a method, return the corresponding registered
        object.
        Args:
            callback (callable/str): Some callback object, or the name of
                some callback.
        Returns:
            dict: "obj": Either the function itself, or the object from which
                        a method comes.
                  "method": The name of the function
        """
        module_logger.debug("lookup_function_or_method: type(callback) {}".format(callback))
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
        

        return {"obj":callback_obj, "method":method_name}

    def unregister(self, fn_or_obj):
        """
        Remove an object from self._asyncHandlers and the _daemon attribute
        Args:
            fn_or_obj (str/function/object): The name of a function, the
                function itself, or an object.
        """
        obj_info = self.lookup(fn_or_obj)
        if len(obj_info) == 0:
            error_msg = "Couldn't find function or object {}".format(fn_or_obj)
            module_logger.error(error_msg)
            raise RuntimeError(error_msg)
        else:
            obj, objectId = obj_info[0]
            del self._asyncHandlers[objectId]
            if objectId in self._daemon.objectsById:
                self._daemon.unregister(objectId)
            else:
                module_logger.debug(
                    "unregister: Didn't unregister object {} from daemon".format(obj)
                )

    def wait_for_callback(self, callback):
        """
        Given some callback registered with the AsnycProxy to be called.
        If there are any return values from the callback, return those.
        Args:
            callback (callable/str):
        Returns:
            None
        """
        res = self.lookup_function_or_method(callback)
        method_name = res["method"]
        obj, _ = self.lookup(res["obj"])[0]
        callback = getattr(obj, method_name)

        while not obj._called[method_name]:
            pass

        obj._called[method_name] = False
        return obj._res[method_name]

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
            self._called[fn.__name__] = True
            res = fn(*args, **kwargs)
            self._res[fn.__name__] = res
            return res

        exposed_wrapper = Pyro4.expose(fn_wrapper)

        class Handler(object):
            def __init__(self):
                self._called = {fn.__name__: False}
                self._res = {fn.__name__: None}

        setattr(Handler, fn.__name__, exposed_wrapper)
        Handler.__name__ = fn.__name__ # not sure this is the best solution
        return Handler
