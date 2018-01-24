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

    # class Handler(object):
    #     pass
        # @classmethod
        # def register_existing_methods(cls, cls_or_obj):
        #     for method_name in dir(cls_or_obj):
        #         method = getattr(cls_or_obj, method_name)
        #         if "_pyroExposed" in dir(method):
        #             if method._pyroExposed:
        #                 print("Setting method: {}".format(method_name))
        #                 setattr(cls, method_name, method)


    __asyncAttributes = frozenset(["_daemon","_daemon_thread","_asyncHandlers"])

    def __init__(self, uri, daemon_details=None):

        Pyro4.core.Proxy.__init__(self, uri)

        # AsyncProxy.Handler.register_existing_methods(self)
        # self._asyncHandlers = AsyncProxy.Handler()

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
            objectId = daemon_details.get("objectId",None)
            self._daemon.register(self._asyncHandler, objectId=objectId)
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
        print("_pyroInvoke: Called. methodname: {}, vargs: {}, kwargs: {}".format(methodname, vargs, kwargs))
        callback = kwargs.pop("callback", None)
        if callback is not None:
            handler = self._asyncHandler
            callback_dict = {}
            if callable(callback):
                method_name = callback.__name__
            elif isinstance(callback, str):
                method_name = callback
            elif isinstance(callback, dict):
                method_name = callback["callback"]
                handler = callback["handler"]

            callback_dict["handler"] = handler
            callback_dict["callback"] = method_name
            kwargs["callback"] = callback_dict

        return super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)


    def register_handlers_with_daemon(self):
        for objectId in self._asyncHandlers:
            if objectId not in self._daemon.objectsById:
                self._daemon.register(self._asyncHandlers[objectId], objectId=objectId)


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
        TODO:
            be able to register entire objects or classes.
        """
        if inspect.isfunction(fn_or_obj):
            objectId = uuid.uuid4()
            handler_class = AsyncProxy.create_handler_class(fn_or_obj)
            cls._asyncHandlers[objectId] = handler_class()
        else:
            objectId = uuid.uuid4()
            cls._asyncHandlers[objectId] = fn_or_obj

    @staticmethod
    def create_handler_class(fn):
        """
        From a non instance method function, create a wrapper class
        Args:
        """
        assert inspect.isfunction(fn), "{} should be of type function, not {}".format(fn, type(fn))

        @functools.wraps(fn)
        def fn_wrapper(self, *args, **kwargs):
            return fn(*args, **kwargs)

        exposed_wrapper = Pyro4.expose(fn_wrapper)

        class Handler(object):
            pass

        setattr(Handler, fn.__name__, exposed_wrapper)

        return Handler
