import unittest
import logging
import time

import Pyro4

from support.logs import setup_logging

from support_pyro.support_pyro4.async.event_emitter import EventEmitter, EventEmitterProxy
from support_pyro.support_pyro4.async.async_proxy import AsyncProxy
from support_pyro.support_pyro4.async import async_callback
from . import test_case_with_server

module_logger = logging.getLogger(__name__)

@Pyro4.expose
class EventEmitterServer(EventEmitter):
    def on(self,*args):
        super(EventEmitterServer, self).on(*args)
    def emit(self,*args):
        super(EventEmitterServer, self).emit(*args)

# @unittest.skip("")
class TestEventEmitter(unittest.TestCase):

    def test_event(self):

        class OnEvent(object):
            def __init__(self):
                self.called = False
            def __call__(self):
                self.called = True
        on_event = OnEvent()
        eventemitter = EventEmitter()
        eventemitter.on("event", on_event)

        eventemitter.emit("event")

        while not on_event.called:
            time.sleep(0.001)
        self.assertTrue(on_event.called)

class TestRemoteEventEmitter(test_case_with_server(
    EventEmitterServer
)):

    def setUp(self):
        class OnEvent(object):
            def __init__(self):
                self.called = False
            @async_callback
            def call(self, res):
                module_logger.debug("call: {}".format(self.__str__()))
                module_logger.debug("{}.call: res: {}".format(self.__class__.__name__, res))
                self.called = True
        self.OnEvent = OnEvent
        self.on_event = OnEvent()

    def tearDown(self):
        self.on_event.called = False

#    @unittest.skip("")
    def test_event(self):
        p = EventEmitterProxy(self.uri)
        p.on("event",self.on_event.call)
        p.emit("event","hello")
        while not self.on_event.called:
            pass
        self.assertTrue(self.on_event.called)

#    @unittest.skip("")
    def test_event_from_server(self):
        p = EventEmitterProxy(self.uri)
        p.on("event",self.on_event.call)
        self.server.emit("event","hello")
        while not self.on_event.called:
            pass
        self.assertTrue(self.on_event.called)

    # @unittest.skip("")
    def test_multiple_handlers(self):
        new_handler = self.OnEvent()
        p = EventEmitterProxy(self.uri)
        p.on("event",self.on_event.call)
        p.on("event",new_handler.call)
        p.emit("event","hello")

        module_logger.debug(self.server._handlers)
        while not self.on_event.called:
            pass
        while not new_handler.called:
            pass

        self.assertTrue(self.on_event.called)
        self.assertTrue(new_handler.called)



if __name__ == "__main__":
    setup_logging()
    unittest.main()
