import unittest

import Pyro4

from support_pyro.support_pyro4.async.async_proxy import AsyncProxy

from . import TestPublisherImplementation
from .. import test_case_with_server

class TestPublisherAsServer(test_case_with_server(
    TestPublisherImplementation
)):
    def setUp(self):
        self.proxy = AsyncProxy(self.uri)
        def handler(res):
            return res
        self.handler = handler

    def tearDown(self):
        self.proxy.stop_publishing()

    def test_start_publishing(self):
        self.proxy.start_publishing(callback=self.handler)
        res = self.proxy.wait_for_callback(self.handler)
        self.assertTrue(res["status"] == "publishing started")

    def test_start_paused_publisher(self):
        def final_handler(res):
            return res
        def pause_handler(res):
            self.proxy.start_publishing(callback=final_handler)
        def start_handler(res):
            self.proxy.pause_publishing(callback=pause_handler)
        self.proxy.register(pause_handler)
        self.proxy.register(final_handler)
        self.proxy.start_publishing(callback=start_handler)
        res = self.proxy.wait_for_callback(final_handler)
        self.assertTrue(res["status"] == "publishing unpaused")
        
    def test_pause_publishing(self):
        self.proxy.start_publishing(callback=self.handler)
        self.proxy.wait_for_callback(self.handler)
        self.proxy.pause_publishing(callback=self.handler)
        res = self.proxy.wait_for_callback(self.handler)
        self.assertTrue(res["status"] == "publishing paused")

    def test_stop_publishing(self):
        def stop_handler(res): return res
        self.proxy.start_publishing(callback=self.handler)
        self.proxy.stop_publishing(callback=stop_handler)
        res = self.proxy.wait_for_callback(stop_handler)
        self.assertTrue(res["status"]=="publishing stopped")

    def test_get_serializer(self):
        serializer = self.proxy.serializer
        self.assertTrue(serializer == Pyro4.util.get_serializer(Pyro4.config.SERIALIZER))

    def test_get_serializer_name(self):
        serializer_name = self.proxy.serializer_name
        self.assertTrue(serializer_name == Pyro4.config.SERIALIZER)

if __name__ == "__main__":
    unittest.main()
