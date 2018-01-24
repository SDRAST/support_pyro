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
