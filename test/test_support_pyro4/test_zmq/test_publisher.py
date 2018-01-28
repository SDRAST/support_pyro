import unittest
import logging
import time
import random

from support_pyro.support_pyro4.zmq import Publisher
from support_pyro.support_pyro4.util import EventEmitter

class TestPublisherImplementation(Publisher):

    def __init__(self,*args, **kwargs):
        super(TestPublisherImplementation, self).__init__(*args, **kwargs)
        self.event_emitter = EventEmitter()

    def publish(self):
        time.sleep(0.1)
        res = {"something random":random.random()}
        self.event_emitter.emit("publish",res)
        return res

    def pause_publishing(self):
        super(TestPublisherImplementation, self).pause_publishing()
        self.event_emitter.emit("pause")

    def unpause_publishing(self):
        super(TestPublisherImplementation, self).unpause_publishing()
        self.event_emitter.emit("unpause")

    def stop_publishing(self):
        super(TestPublisherImplementation, self).stop_publishing()
        self.event_emitter.emit("stop")


class TestPublisher(unittest.TestCase):

    def setUp(self):
        self.publisher = TestPublisherImplementation()

    def tearDown(self):
        self.publisher.stop_publishing()


    def test_serializer(self):
        pass

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
