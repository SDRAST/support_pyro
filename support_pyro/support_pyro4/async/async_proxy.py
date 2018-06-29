import time
import uuid      # immutable UUID objects, functions for generating UUIDs
import logging
import functools
import threading # provides execution threads, thread locks, etc.
import inspect   # gets information about live Python objects

import Pyro4

from .async_callback_manager import AsyncCallbackManager
from .async_callback import async_callback

__all__ = ["AsyncProxy"]

pyro4_version_info = Pyro4.__version__.split(".")

module_logger = logging.getLogger(__name__)
module_logger.debug("from {}".format(__name__))

class AsyncProxy(Pyro4.core.Proxy):
    """
    Proxy that has a Pyro4 Daemon attached to it that registers methods.

    
    A proxy is a connection to a remote Pyro server object. The remote object
    is typically an instance of a class. This modified proxy associates 
    functions with the proxy so that, when a method of the remote object is
    called, a local function handles the returned data.  These handlers are
    associated with the remote object's methods.  For each remote method there
    can be one or more handlers.
    
    This is not meant to be subclassed directly. Instead, if you'd like to
    access proxy methods/properties in a "Client" class, do so as follows::
      class Client(object):
          def __init__(self, uri):
              self.proxy = AsyncProxy(uri)
          def __getattr__(self, attr):
              return getattr(self.proxy, attr)
    
    Attributes::
      __asyncAttributes (frozenset): List of protected attributes.
      _asyncHandlers - dict with details of the handlers
      _daemon        - Pyro4.Daemon
      _daemon_thread - threading.Thread for the daemon
    
    The keys for _asyncHandlers are objectIDs.  The value associated with a key
    is a dict with keys::
      "object" - the name of the remote object
      "uri"    - the Pyro URI of the remote object
      
    This is for passing callbacks to servers, such that the server can call
    client-side functions. This will register functions/methods on the fly.

    Examples:

    .. code-block:: python

        # async_server.py
        from support.pyro import async

        class AsyncServer(object):

            @async.async_method
            def async_method(self, *args):
                self.async_method.cb(args) # bounce back whatever is sent

        async_server = AsyncServer()
        async_server.launch_server(ns=False,objectId="AsyncServer",objectPort=9092)

    We could access this server as follows:

    .. code-block:: python

        # async_client.py

        def handler(res):
            print("Got {} from server!".format(res))

        async_client = AsyncProxy("PYRO:AsyncServer@localhost:9092")
        async_client.async_method(5,callback=handler)
        while True:
            pass

    Note that the last bit is necessary if running inside a script, otherwise
    the client program will exit before the handler function can be called.
    """
    __asyncAttributes = frozenset(
        ["_daemon","_daemon_thread","_asyncHandlers"]
    )
    def __init__(self, uri, daemon_details=None):
        """
        Create an AsyncProxy object and start it's daemon's thread
        
        @param uri : URI for the server
        @type  uri : Pyro4.URI object
        
        @param daemon_details : properties of a pre-existing daemon
        @type  daemon_details : dict
        """
        Pyro4.core.Proxy.__init__(self, uri)

        self._asyncHandlers = {}
        # get/make Pyro4.Daemon object
        if daemon_details is None:
            # no daemon provided; create one
            self._daemon = Pyro4.Daemon()
        else:
            if "daemon" in daemon_details:
                # a daemon is provided
                self._daemon = daemon_details["daemon"]
            else:
                # only a host and port are provided for a daemon
                #   get host and port with defaults None and 0
                host = daemon_details.get("host", None)
                port = daemon_details.get("port",0)
                self._daemon = Pyro4.Daemon(host=host, port=port)
        # self.register_handlers_with_daemon()
        self._daemon_thread = threading.Thread(target=self._daemon.requestLoop)
        self._daemon_thread.daemon = True
        self._daemon_thread.start()

    def __getattr__(self, name):
        """
        get the value of a custom __asyncAttributes item
        
        @param name : attribute key
        @type  name : str
        
        @return: attribute value
        """
        if name in AsyncProxy.__asyncAttributes:
            return super(Pyro4.core.Proxy, self).__getattribute__(name)
        return Pyro4.core.Proxy.__getattr__(self, name)

    def __setattr__(self, name, value):
        """
        set the value of a custom __asyncAttributes item
        
        @param name : attribute key
        @type  name : str
        
        @param value : value of the dict item
        @type  value : object
        """
        if name in AsyncProxy.__asyncAttributes:
            return object.__setattr__(self, name, value)
        return Pyro4.core.Proxy.__setattr__(self, name, value)

    def _pyroInvoke(self, methodname, vargs, kwargs, flags=0, objectId=None):
        """
        Override the Pyro4.Proxy _pyroInvoke method.
        
        _pyroInvoke performs the remote method call communication
        
        Keyword arguments that are not in ["callback", "cb_info", "cb"] are
        passed to the remote method.
        
        This will modify the kwargs dictionary to automatically include a 
        reference to the self._asyncHandler attribute.
        
        @param methodname : name of the remote method
        @type  methodname : str
        
        @param vargs : positional arguments for the remote method call
        @type  vargs : tuple
        
        @param kwargs : keyword arguments for the call, and for callback
        @type  kwargs : dict
        """
        #module_logger.debug(
        #  "_pyroInvoke: Called. methodname: {}, vargs: {}, kwargs: {}".format(
        #                                            methodname, vargs, kwargs))
        if kwargs is not None:
            # look for details on the callback
            callback = None
            for key in ["callback", "cb_info", "cb"]:
                if key in kwargs:
                    # callback key found; remove item from kwargs
                    callback = kwargs.pop(key)
                    break
            # if callback data was found then process it.
            if callback is not None:
                callback_dict = {}
                # get remote method's name and local callback function
                res = self.lookup_function_or_method(callback)
                callback_obj = res["obj"]    # remote object
                method_name = res["method"]  # remote object's method name
                # register the callback
                #module_logger.debug("_pyroInvoke: calling register")
                obj, _ = self.register(callback_obj)[0]
                self.register_handlers_with_daemon()
                callback_dict["cb_handler"] = obj
                callback_dict["cb"] = method_name
                kwargs["cb_info"] = callback_dict
        # now call the specified method of the remote object
        #module_logger.debug(
        #         "_pyroInvoke: "+
        #         "calling super, methodname: {}, vargs: {}, kwargs: {}".format(
        #                                            methodname, vargs, kwargs))
        resp = super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)
        #module_logger.debug("_pyroInvoke: super called. resp: {}".format(resp))
        return resp

    def shutdown(self):
        """
        proxy for the daemon shutdown method.
        """
        self._daemon.shutdown()

    def register_handlers_with_daemon(self):
        """
        Register all the objects in _asyncHandlers with the _daemon attribute
        """
        #module_logger.debug("register_handlers_with_daemon:"+
        #                       " self._daemon.objectsById (before): {}".format(
        #                                list(self._daemon.objectsById.keys())))
        #module_logger.debug("register_handlers_with_daemon:"+
        #                                     " self._asyncHandlers: {}".format(
        #                                     list(self._asyncHandlers.keys())))
        for objectId in self._asyncHandlers:
            obj = self._asyncHandlers[objectId]["object"]
            if objectId not in self._daemon.objectsById and \
                                                   not hasattr(obj, "_pyroId"):
                # if not already registered
                module_logger.debug("register_handlers_with_daemon:"+
                           " Registering object {} with objectId {}...".format(
                                       obj.__class__.__name__, objectId[4:11]))
                # register the object with the proxy's daemon and get its URI
                uri = self._daemon.register(obj, objectId=objectId)
                self._asyncHandlers[objectId]["uri"] = uri
                
        #module_logger.debug("register_handlers_with_daemon:"+
        #                        " self._daemon.objectsById (after): {}".format(
        #                                list(self._daemon.objectsById.keys())))

    def register(self, *fn_or_objs):
        """
        Register functions (not methods) with the AsyncProxy.
        
        The function will get wrapped up in an exposed class, and the object 
        will be registered as is.
        
        @param fn_or_objs : list of functions/objects or single function/object
        @type  fn_or_objs : list or callable
        
        @return: list of [obj, objectId] lists.
        """
        module_logger.debug("register: called")
        return_vals = []
        for fn_or_obj in fn_or_objs:
            # this is the same signature as Pyro4.core.Daemon
            objectId = "obj_" + uuid.uuid4().hex 
            #module_logger.debug("register:"+
            #                      " creating objectId {}... for obj {}".format(
            #                                        objectId[4:11], fn_or_obj))
            if inspect.isfunction(fn_or_obj):
                # if fn_or_obj is an unbound function, convert it to a class
                # instance
                handler_class = AsyncProxy.create_handler_class(fn_or_obj)
                handler_obj = handler_class()
            else:
                # fn_or_obj is already a class instance
                handler_obj = fn_or_obj
            # set the handler objects ID if necessary
            if not hasattr(handler_obj, "_objectHandlerId"):
                handler_obj._objectHandlerId = objectId
            # create a dict for the object in _asyncHandlers
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
        Returns the remote object associated with some function or object
        
        Given some function name, look it up in self._asyncHandlers, and
        return the object to which it refers.
        
        @param fn_or_obj: name of a function, the function itself, or an object
        @type  fn_or_obj: str/function/object
               
        Returns:
            [[object, objectId]], or []
        """
        module_logger.debug("lookup: "+
                                 "type(fn_or_obj): {}".format(type(fn_or_obj)))
        module_logger.debug("lookup: "+
                           "hasattr(fn_or_obj, '_objectHandlerId'): {}".format(
                                       hasattr(fn_or_obj, '_objectHandlerId')))
        result = []
        for objectId in self._asyncHandlers:
            # get the object from the list of handlers
            obj = self._asyncHandlers[objectId]["object"]
            if hasattr(fn_or_obj, "_objectHandlerId"):
                # fn_or_obj has the _objectHandlerId attribute; does it match?
                if fn_or_obj._objectHandlerId == objectId:
                    result.append([obj, objectId])
            elif isinstance(fn_or_obj, str):
                # fn_or_obj is a string, presumably its name; does it match?
                if obj.__class__.__name__ == fn_or_obj:
                    result.append([obj, objectId])
            elif inspect.isfunction(fn_or_obj):
                # fn_or_obj is a function; we can only lookup by name
                if obj.__class__.__name__ == fn_or_obj.__name__:
                    result.append([obj, objectId])
            else:
                # fn_or_obj is same class as obj; assume they are associated
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
            dict: dictionary with the following keys/values:
                * "obj": Either the function itself, or the object from which
                    a method comes.
                * "method": The name of the function
        """
        #module_logger.debug("lookup_function_or_method:"+
        #                                 " type(callback) {}".format(callback))
        if isinstance(callback, str):
            # the callback name is given
            #   attempt to find the callback in the global context
            callback_obj = globals()[callback]
            method_name = callback
        elif inspect.ismethod(callback):
            # if the callback itself is given and is a method, get its name
            callback_obj = callback.im_self
            method_name = callback.__name__
        elif inspect.isfunction(callback):
            # if the callback itself is given and is a function, get its name
            callback_obj = callback
            method_name = callback.__name__
        return {"obj":callback_obj, "method":method_name}

    def unregister(self, fn_or_obj):
        """
        Remove an object from self._asyncHandlers and the _daemon attribute
        
        @param fn_or_obj : name of function, the function itself, or an object
        @type  fn_or_obj : str or function or object
        """
        # get the entry in for fn_or_obj in _asyncHandlers
        obj_info = self.lookup(fn_or_obj)
        # obj_info is a list of all the matching entries
        if len(obj_info) == 0:
            # this should not happen
            error_msg = "Couldn't find function or object {}".format(fn_or_obj)
            module_logger.error(error_msg)
            raise RuntimeError(error_msg)
        else:
            # there should be only one entry
            obj, objectId = obj_info[0]
            del self._asyncHandlers[objectId]
            if objectId in self._daemon.objectsById:
                self._daemon.unregister(objectId)
            else:
                module_logger.debug("unregister:"+
                        " Didn't unregister object {} from daemon".format(obj))

    def wait(self, callback):
        """
        Given some callback registered with the AsnycProxy to be called.
        If there are any return values from the callback, return those.

        Args:
            callback (callable/str):
        Returns:
            None
        """
        # this returns a dict with keys 'obj' and 'method'.
        res = self.lookup_function_or_method(callback)
        method_name = res["method"]
        # returns a list of [object, objectID] items (only one item expected)
        # ignore the second item of the first (and only?) item
        obj, _ = self.lookup(res["obj"])[0]
        # the callback is the value of the attribute method_name of obj
        callback = getattr(obj, method_name)

        while not obj._called[method_name]:
            # sit and do nothing until method 'method_name' has been called
            pass
        # the method was called; reset it to not called
        obj._called[method_name] = False
        # and return the result of the call
        return obj._res[method_name]

    @staticmethod
    def create_handler_class(func):
        """
        Create a wrapper class from an unbound function
        
        staticmethod() returns a staticmethod which does not have an implicit
        first argument (self). I can be used to process class attributes that
        span class instances.
        
        @param fn : function that will get exposed and wrapped in a class.
        @type  fn : callable
        """
        assert inspect.isfunction(fn), \
                   "{} should be of type function, not {}".format(fn, type(fn))
        module_logger.debug("AsyncProxy.create_handler_class:"+
                          " Creating handler class for function {}".format(fn))
                          
        # wraps gives fn_wrapper (e.g. docstring) the properties of fn
        @functools.wraps(fn)
        def fn_wrapper(self, *args, **kwargs):
            # adds dict _called as an attribute
            #   sets it to True for the wrapped function
            self._called[fn.__name__] = True
            # calls the function
            res = fn(*args, **kwargs)
            # adds dict _res as an attritube
            #   sets it to result of function call for
            self._res[fn.__name__] = res
            return res
        # expose the wrapped function to the remote clients
        exposed_wrapper = Pyro4.expose(fn_wrapper)
        # create an empty class and define attributes _called and _set
        class Handler(object):
            def __init__(self):
                self._called = {fn.__name__: False}
                self._res = {fn.__name__: None}
        # set the attribute fn.__name__ (the name of the wrapped function) of 
        # Handler to exposed_wrapper, i.e., define a method for Handler
        setattr(Handler, fn.__name__, exposed_wrapper)
        # the name of the Handler class will be the function name
        Handler.__name__ = fn.__name__ # not sure this is the best solution

        return Handler
