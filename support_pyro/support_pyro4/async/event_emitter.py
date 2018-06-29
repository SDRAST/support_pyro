"""
execute a function on the occurrence of an event

Example::
  # from support.pyro.async.event_emitter import EventEmitter  -- not from ipython command line
  from support.pyro.support_pyro.support_pyro4.async.event_emitter import EventEmitter

  def some_callback():
    print "callback executed"

  ee = EventEmitter()
  ee.on("anevent", some_callback)
  ee.emit("anevent")
"""
import logging
import threading

import Pyro4

from .async_proxy import AsyncProxy

module_logger = logging.getLogger(__name__)

__all__ = ["EventEmitter","EventEmitterProxy"]

class EventEmitter(object):
    """
    class to execute one or more functions when an event occurs

    Attributes:
      _handlers (list): functions associated with events
      _lock (threading.Lock): locks the thread
      threaded (bool): this emitter works in a thread if True (default)
    """
    def __init__(self, threaded=True):
        """
        initialization

        @param threaded : execute the event in a thread
        @type  threaded : bool
        """
        self.threaded = threaded
        self._lock = threading.Lock()
        self._handlers = {}

    def emit(self, event_name, *args, **kwargs):
        """
        execute the handler function
        
        @param event_name : event identifier
        @type  event_name : str
        
        @param *args : positional arguments to pass to the handler(s)
        
        @param **kwargs : keyword arguments to pass to the handler(s)
        """
        module_logger.debug("emit: called. event_name: {}".format(event_name))
        def emitter():
            # process an event
            if event_name in self._handlers:
                # only if a handler is defined forthe event
                handlers_to_remove = []
                for handler_dict in self._handlers[event_name]:
                    handler = handler_dict["handler"]
                    once = handler_dict["once"]
                    if once:
                        handlers_to_remove.append(handler_dict)
                    with self._lock:
                        module_logger.debug(
                            "emit: handler {} for event {}".format(handler,event_name)
                        )
                        if isinstance(handler, dict):
                            handler_obj = handler["cb_handler"]
                            handler_method_name = handler["cb"]
                            handler = getattr(handler_obj, handler_method_name)
                        try:
                            handler(*args, **kwargs)
                        except Pyro4.errors.ConnectionClosedError as err:
                            # this means that we're attempting to call a handler
                            # that was registered from proxy that we're no longer
                            # connected to.
                            handlers_to_remove.append(handler_dict)
                self._cleanup(event_name, handlers_to_remove)
            else: # just to show where the conditional block ends
                pass
                
        if self.threaded:
            t = threading.Thread(target=emitter)
            t.daemon = False
            t.start()
        else:
            emitter()

    def on(self, event_name, callback, once=False):
        """
        register a handler for an event
        
        @param event_name : event identifier
        @type  event_name : str
        
        @param callback : action to perform
        @type  callback : function
        """
        module_logger.debug("on: called. event_name: {}, callback: {}".format(
            event_name, callback
        ))
        with self._lock:
            if event_name not in self._handlers:
                # create an empty list of handlers for a new event
                self._handlers[event_name] = []
            self._handlers[event_name].append({"handler":callback, "once":once})

    def once(self, *args):
        """register a handler for an event. Once it gets called, it gets removed.
        """
        self.on(*args, once=True)

    def _cleanup(self, event, handlers_to_remove):
        """
        Given some handlers registered to an event, remove the handlers in
        handlers_to_remove

        Args:
            event (str): name of event in self._handlers
            handlers_to_remove (list): handlers to remove from _handlers[event]

        Returns: None
        """
        if event not in self._handlers:
            return
        for handler in handlers_to_remove:
            if handler in self._handlers[event]:
                self._handlers[event].remove(handler)


class EventEmitterProxy(AsyncProxy):
    """
    Extension to AsyncProxy that allows us to interact with
    EventEmitters as servers.

    21-03-2018: This is largly untested and unproven.
    """
    def on(self, event, callback, **kwargs):
        """
        when event occurs execute callback with the specified keyword arguments
        
        @param event :
        """
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