import logging
import time
import unittest

from . import TestSubscriberImplementation, TestPublisherImplementation
from .. import test_case_with_server
from ... import setup_logging

class TestSubscriber(test_case_with_server(TestPublisherImplementation)):

    def setUp(self):
        self.proxy = TestSubscriberImplementation(self.uri)
        class Handler(object):
            def __init__(self):
                self.called = False
            def __call__(self, res):
                self.called = True
                return res
        self.handler = Handler()
        self.proxy.on("consume", self.handler)

    def test_start_subscribing(self):
        self.proxy.start_subscribing()
        while not self.handler.called:
            pass
        self.assertTrue(self.handler.called)

    @unittest.skip("")
    def test_pause_subscribing(self):
        self.proxy.pause_subscribing()

    @unittest.skip("")
    def test_unpause_subscribing(self):
        self.proxy.unpause_subscribing()

    @unittest.skip("")
    def test_stop_subscribing(self):
        self.proxy.stop_subscribing()

    @unittest.skip("")
    def test_consume(self):
        res = self.proxy.consume("hello")
        print("test_consume: {}".format(self.handler.called))
        self.assertTrue(res == "hello")

    @unittest.skip("")
    def test_consume_msg(self):
        serializer = self.server._serializer
        res = self.server.publish()
        msg = serializer.dumps(res)
        consumed = self.proxy._consume_msg(msg)
        self.assertTrue(res, consumed)

if __name__ == "__main__":
    setup_logging(logLevel=logging.DEBUG)
    logging.getLogger("Subscriber").setLevel(logging.DEBUG)
    unittest.main()
