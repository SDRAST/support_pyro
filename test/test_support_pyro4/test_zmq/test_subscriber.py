import unittest

from . import TestSubscriberImplementation, TestPublisherImplementation
from .. import test_case_with_server

class TestSubscriber(test_case_with_server(TestPublisherImplementation)):

    def setUp(self):
        self.proxy = TestSubscriberImplementation(self.uri)
        # called = {
        #     "handler":False
        # }
        class Handler(object):
            def __init__(self):
                self.called = False
            def __call__(self, res):
                print("Handler.__call__: {}".format(res))
                self.called = True
                print("Handler.__call__: {}".format(self.called))
                return res

        self.handler = Handler()
        # def handler(res):
        #     print("from handler: {}".format(res))
        #     called["handler"] = True
        #     print("from handler: {}".format(called))
        # self.called = called
        self.proxy.emitter.on("consume", self.handler)

    def test_start_subscribing(self):
        self.proxy.start_subscribing()
        print("test_start_subscribing: {}".format(self.handler.called))
        while not self.handler.called:
            pass
        self.assertTrue(self.handler.called)

    def test_pause_subscribing(self):
        self.proxy.pause_subscribing()

    def test_unpause_subscribing(self):
        self.proxy.unpause_subscribing()

    def test_stop_subscribing(self):
        self.proxy.stop_subscribing()

    def test_consume(self):
        res = self.proxy.consume("hello")
        print("test_consume: {}".format(self.handler.called))
        self.assertTrue(res == "hello")

    def test_consume_msg(self):
        serializer = self.server._serializer
        res = self.server.publish()
        msg = serializer.dumps(res)
        consumed = self.proxy._consume_msg(msg)
        self.assertTrue(res, consumed)

if __name__ == "__main__":
    unittest.main()
