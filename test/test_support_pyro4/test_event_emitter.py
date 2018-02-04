import unittest
import time

from support_pyro.support_pyro4.util import EventEmitter

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

if __name__ == "__main__":
    unittest.main()
