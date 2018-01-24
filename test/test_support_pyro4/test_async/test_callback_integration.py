import threading
import unittest

import Pyro4

from src.async_proxy import AsyncProxy
from . import test_case_factory, SimpleAsyncServer

class TestCallbackIntegration(test_case_factory(SimpleAsyncServer)):

    @unittest.skip("")
    def test_callback_integration_register_function(self):

        def callback(res):
            print("callback: res: {}".format(res))
            callback.called = True
            self.assertTrue(res=="hello")

        callback.called = False

        AsyncProxy.register(callback)
        proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        proxy.ping_with_response(callback=callback)

        while not callback.called:
            pass

    def test_callback_integration_inside_subclass(self):

        called = {
            "callback": False
        }

        class AsyncProxySubClass(AsyncProxy):

            test_case = self

            @Pyro4.expose
            def callback(self, res):
                called["callback"] = True
                self.test_case.assertTrue(res == "hello")

        proxy = AsyncProxySubClass("PYRO:SimpleAsyncServer@localhost:50000")

        proxy.ping_with_response(callback="callback")

        while not called["callback"]:
            pass
        self.assertTrue(called["callback"])

    # @unittest.skip("")
    def test_callback_integration_register_class(self):

        called = {
            "callback1": False,
            "callback2": False
        }

        class Callbacks(object):

            test_case = self

            def callback1(self, res):
                called["callback1"] = True
                self.test_case.assertTrue(res == "hello")

            def callback2(self, res):
                called["callback2"] = True
                self.test_case.assertTrue(res == "hello")

        callbacks = Callbacks()
        AsyncProxy.register(callbacks)


if __name__ == "__main__":
    unittest.main()
