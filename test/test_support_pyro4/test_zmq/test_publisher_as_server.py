import unittest

from support_pyro.support_pyro4.async.async_proxy import AsyncProxy

from . import TestPublisherImplementation
from .. import test_case_with_server

class TestPublisherAsServer(test_case_with_server(
    TestPublisherImplementation
)):
    def setUp(self):
        self.proxy = AsyncProxy(self.uri)

    def tearDown(self):
        pass

    def test_start_publishing(self):

        def handler(res):
            return res

        self.proxy.start_publishing(callback=handler)
        res = self.proxy.wait_for_callback(handler)
        self.assertTrue(res == "publishing started")
        
if __name__ == "__main__":
    unittest.main()
