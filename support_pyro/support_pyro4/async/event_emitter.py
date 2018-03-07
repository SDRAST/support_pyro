import logging
import threading

from .async_proxy import AsyncProxy

module_logger = logging.getLogger(__name__)

__all__ = ["EventEmitter","EventEmitterProxy"]

class EventEmitter(object):

    def __init__(self, threaded=True):
        self.threaded = threaded
        self._lock = threading.Lock()
        self._handlers = {}

    def emit(self, event_name, *args, **kwargs):
        module_logger.debug("emit: called. event_name: {}".format(event_name))
        def emitter():
            if event_name in self._handlers:
                for handler in self._handlers[event_name]:
                    with self._lock:
                        module_logger.debug(
                            "Emitting handler {} for event {}".format(handler,event_name)
                        )
                        if isinstance(handler, dict):
                            handler_obj = handler["cb_handler"]
                            handler_method_name = handler["cb"]
                            handler = getattr(handler_obj, handler_method_name)
                            module_logger.debug("emit: handler: {}, method_name: {}".format(handler, handler_method_name))
                        handler(*args, **kwargs)

        if self.threaded:
            t = threading.Thread(target=emitter)
            t.daemon = True
            t.start()
        else:
            emitter()

    def on(self, event_name, callback):
        module_logger.debug("on: called. event_name: {}, callback: {}".format(
            event_name, callback
        ))
        with self._lock:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            self._handlers[event_name].append(callback)

class EventEmitterProxy(AsyncProxy):
    """
    Extension to AsyncProxy that allows us to interact with
    EventEmitters as servers.
    """
    def on(self,event,callback,**kwargs):
        module_logger.debug("on: called for event {}".format(event))
        res = self.lookup_function_or_method(callback)
        callback_obj = res["obj"]
        method_name = res["method"]

        obj, _ = self.register(callback_obj)[0]
        self.register_handlers_with_daemon()

        callback_dict = {
            "cb_handler":obj,
            "cb":method_name
        }
        return self._pyroInvoke("on",(event, callback_dict), kwargs)

    # def emit(self, *args, **kwargs):
    #     module_logger.debug("emit: called for event {}".format(args[0]))
    #     self._pyroInvoke("emit", args, kwargs)
