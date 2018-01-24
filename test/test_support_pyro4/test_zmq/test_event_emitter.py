import unittest
import time

from pyro4_zmq.event_emitter import EventEmitter

class TestEventEmitter(unittest.TestCase):

    def test_event(self):

        def on_event():
            on_event.called = True

        eventemitter = EventEmitter()
        eventemitter.on("event", on_event)

        eventemitter.emit("event")

        while not on_event.called:
            time.sleep(0.001)
        self.assertTrue(on_event.called)

if __name__ == "__main__":
    unittest.main()
