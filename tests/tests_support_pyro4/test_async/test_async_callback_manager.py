import unittest
import threading
import importlib

import Pyro4

from support_pyro.support_pyro4.async import (
    AsyncCallbackManager,
    AsyncProxy,
    async_callback
)

from . import SimpleAsyncServer
from .. import test_case_with_server

class AsyncCallbackManagerSub(AsyncCallbackManager):

    @async_callback
    def method_async(self, res):
        pass

    @async_callback
    def method_async1(self, res):
        pass

    def method_sync(self):
        pass

class TestAsyncCallbackManager(test_case_with_server(SimpleAsyncServer)):

    def test_init(self):
        client = AsyncCallbackManagerSub()
        self.assertTrue("method_async" in client._called)
        self.assertTrue("method_sync" not in client._called)

    def test_wait(self):
        client = AsyncCallbackManagerSub()
        proxy = AsyncProxy(self.uri)
        with client.wait("method_async"):
            proxy.ping_with_response(callback=client.method_async)
        with client.wait(client.method_async):
            proxy.ping_with_response(callback=client.method_async)
if __name__ == "__main__":
    unittest.main()
