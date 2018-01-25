class AsyncProxy(Pyro4.core.Proxy):
    """
    Proxy that has a Pyro4 Daemon attached to it that registers methods.
    """
    _asyncHandlers = {}

    class Handler(object):

        @classmethod
        def register_existing_methods(cls, cls_or_obj):
            for method_name in dir(cls_or_obj):
                method = getattr(cls_or_obj, method_name)
                if "_pyroExposed" in dir(method):
                    if method._pyroExposed:
                        print("Setting method: {}".format(method_name))
                        setattr(cls, method_name, method)

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
                handler, handler_id = self.lookup(method_name)
            elif isinstance(callback, str):
                method_name = callback
                handler, handler_id = self.lookup(method_name)
            elif inspect.ismethod(callback):
                method_name = callback.__name__
                handler = callback.im_self
            if isinstance(callback, dict):
                method_name = callback["callback"]
                handler = callback["handler"]
            callback_dict["cb_handler"] = handler
            callback_dict["cb"] = method_name
            kwargs["cb_info"] = callback_dict

        module_logger.debug("_pyroInvoke: calling super, kwargs: {}".format(kwargs))
        resp = super(AsyncProxy, self)._pyroInvoke(methodname,
                                            vargs, kwargs,
                                            flags=flags,
                                            objectId=objectId)
        module_logger.debug("_pyroInvoke: super called. resp: {}".format(resp))
        return resp
