import unittest

from . import TestSubscriberImplementation, TestPublisherImplementation
from .. import test_case_with_server

class TestSubscriber(test_case_with_server(TestPublisherImplementation)):

    def setUp(self):
        self.proxy = TestSubscriberImplementation(self.uri)

    def test_start_subscribing(self):
        pass

    def test_pause_subscribing(self):
        pass

    def test_unpause_subscribing(self):
        pass

    def test_stop_subscribing(self):
        pass

    def test_consume(self):
        pass

    def test_consume_msg(self):
        serializer = self.server._serializer
        res = self.server.publish()
        msg = serializer.dumps(res)
        consumed = self.proxy._consume_msg(msg)
        self.assertTrue(res, consumed)

if __name__ == "__main__":
    unittest.main()
