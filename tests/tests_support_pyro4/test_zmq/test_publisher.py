import unittest
import logging
import time
import random

import Pyro4

from support_pyro.support_pyro4.zmq.publisher import PublisherThread

from . import (TestPublisherImplementation,
              TestMultiSocketPublisherManagerImplementation,
              TestSingleSocketPublisherManagerImplementation)

# @unittest.skip("")
class TestPublisherThread(unittest.TestCase):

    def setUp(self):
        def callback(res):
            time.sleep(0.1)
            return res

        self.callback = callback
        self.test_thread = PublisherThread(target=self.callback, args=("hello",))

    def tearDown(self):
        self.test_thread.stop()
        self.test_thread.join()

    def test_start(self):
        self.test_thread.start()
        self.assertTrue(self.test_thread.running())

    def test_pause(self):
        self.test_thread.start()
        self.test_thread.pause()
        self.assertTrue(self.test_thread.paused())
        self.test_thread.unpause()
        self.assertFalse(self.test_thread.paused())

# @unittest.skip("")
class TestPublisher(unittest.TestCase):

    def setUp(self):
        self.publisher = TestPublisherImplementation()

    def tearDown(self):
        self.publisher.stop_publishing()

    def test_serializer(self):
        self.assertTrue(self.publisher._serializer_name == Pyro4.config.SERIALIZER)
        self.assertTrue(self.publisher._serializer == Pyro4.util.get_serializer(Pyro4.config.SERIALIZER))

    def test_start_publishing(self):

        def on_publish(res):
            on_publish.called = True

        on_publish.called = False

        self.publisher.emitter.on("publish", on_publish)
        self.publisher.start_publishing()

        while not on_publish.called:
            pass

        self.assertTrue(on_publish.called)
        self.publisher.stop_publishing()

    def test_pause_publishing(self):

        def on_pause():
            on_pause.called = True
        on_pause.called = False

        self.publisher.emitter.on("pause", on_pause)
        self.publisher.start_publishing()
        self.publisher.pause_publishing()

        while not on_pause.called:
            pass

        self.assertTrue(on_pause.called)

    def test_stop_publishing(self):

        def on_stop():
            on_stop.called = True
        on_stop.called = False

        self.publisher.start_publishing()
        self.publisher.publisher_thread.event_emitter.on("stop", on_stop)
        self.publisher.stop_publishing()

        while not on_stop.called:
            pass

        self.assertTrue(on_stop.called)

def handler_factory(name=None):
    class handler(object):
        def __init__(self, name):
            self.name = name
            self.called = False
        def __call__(self, res):
            self.called = True
    return handler(name)

def test_multi_publisher_factory(publisher_cls):

    class TestMultiPublisherMananger(unittest.TestCase):
        def setUp(self):
            self.publisher = publisher_cls()

        def tearDown(self):
            self.publisher.stop_publishing()

        def test_serializer(self):
            serializer_names = self.publisher.serializer_name
            serializers = self.publisher.serializer

            for name in serializer_names:
                self.assertTrue(serializer_names[name] == Pyro4.config.SERIALIZER)
                self.assertTrue(serializers[name] == Pyro4.util.get_serializer(Pyro4.config.SERIALIZER))

        # @unittest.skip("")
        def test_start_publishing(self):
            on_publish_handlers = []
            for p in self.publisher.publishers:
                handler = handler_factory(p.name)
                on_publish_handlers.append(handler)
                p.emitter.on("publish", handler)

            self.publisher.start_publishing()
            while not all(h.called for h in on_publish_handlers):
                pass

            for handler in on_publish_handlers:
                self.assertTrue(handler.called)

        # @unittest.skip("")
        def test_pause_publishing(self):
            on_pause_handlers = []
            for p in self.publisher.publishers:
                handler = handler_factory(p.name)
                on_pause_handlers.append(handler)
                p.emitter.on("publish", handler)

            self.publisher.start_publishing()
            while not all(h.called for h in on_pause_handlers):
                pass

            for handler in on_pause_handlers:
                self.assertTrue(handler.called)

        # @unittest.skip("")
        def test_stop_publishing(self):
            on_stop_handlers = []
            for p in self.publisher.publishers:
                handler = handler_factory(p.name)
                on_stop_handlers.append(handler)
                p.emitter.on("publish", handler)

            self.publisher.start_publishing()
            while not all(h.called for h in on_stop_handlers):
                pass

            for handler in on_stop_handlers:
                self.assertTrue(handler.called)

    return TestMultiPublisherMananger

# @unittest.skip("")
class TestMultiSocketPublisherManager(test_multi_publisher_factory(
    TestMultiSocketPublisherManagerImplementation
)):
    pass

class TestSingleSocketPublisherManager(test_multi_publisher_factory(
    TestSingleSocketPublisherManagerImplementation
)):
    pass

if __name__ == "__main__":
    logging.basicConfig()
    unittest.main()
