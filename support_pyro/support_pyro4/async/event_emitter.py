import logging
import threading

from .async_proxy import AsyncProxy

module_logger = logging.getLogger(__name__)

class EventEmitter(object):

    def __init__(self, threaded=True):
        self.threaded = threaded
        self._lock = threading.Lock()
        self._handlers = {}

    def emit(self, event_name, *args, **kwargs):
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
        res = self.lookup_function_or_method(callback)
        callback_obj = res["obj"]
        method_name = res["method"]

        obj, _ = self.register(callback_obj)[0]
        self.register_handlers_with_daemon()

        callback_dict = {
            "cb_handler":obj,
            "cb":method_name
        }
        return self._pyroInvoke("on",(event, callback_dict),kwargs)
