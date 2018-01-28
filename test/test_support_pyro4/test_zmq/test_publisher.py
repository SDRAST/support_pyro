import unittest
import logging
import time
import random

import Pyro4

from . import TestPublisherImplementation

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
            # print("res from on_publish: {}".format(res))
            on_publish.called = True
            on_publish.count += 1

        def on_start(publisher):
            pass

        on_publish.count = 0
        on_publish.called = False

        self.publisher.event_emitter.on("publish", on_publish)
        self.publisher.start_publishing(callback=on_start)

        while not on_publish.called:
            pass

        self.assertTrue(on_publish.called)
        self.publisher.stop_publishing()

    def test_pause_publishing(self):

        def on_pause():
            on_pause.called = True
        on_pause.called = False

        self.publisher.event_emitter.on("pause", on_pause)
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

if __name__ == "__main__":
    logging.basicConfig()
    unittest.main()
