import logging
import threading
import unittest

import Pyro4

from ... import setup_logging
setup_logging(logging.getLogger(), logLevel=logging.INFO)

from support_pyro.support_pyro4.async.async_proxy import AsyncProxy
from . import test_case_factory, SimpleAsyncServer

class TestCallbackIntegration(test_case_factory(SimpleAsyncServer)):

    def setUp(self):
        self.logger = logging.getLogger("TestCallbackIntegration")
        self.proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")

    def tearDown(self):
        self.proxy.shutdown()

    # @unittest.skip("")
    def test_callback_integration_register_function(self):
        called = {
            "callback":False,
            "handler": False
        }
        def callback(res):
            self.logger.info("callback: res: {}".format(res))
            called["callback"] = True
            self.assertTrue(res=="hello")

        def handler(res):
            self.logger.info("handler: res: {}".format(res))
            called["handler"] = True
            self.assertTrue(res=="hello")


        AsyncProxy.register(callback)
        AsyncProxy.register(handler)
        proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        proxy.ping_with_response(callback=callback)
        proxy.ping_with_response(callback=handler)
        while not (called["callback"] and called["handler"]):
            pass

    # @unittest.skip("")
    def test_callback_integration_register_obj(self):

        class Callbacks(object):
            test_case = self
            called = {
                "callback1": False,
                "callback2": False
            }

            @Pyro4.expose
            def callback1(self, res):
                self.test_case.logger.info("callback1: Called. res: {}".format(res))
                self.called["callback1"] = True
                self.test_case.assertTrue(res == "hello")

            @Pyro4.expose
            def callback2(self, res):
                self.test_case.logger.info("callback2: Called. res: {}".format(res))
                self.called["callback2"] = True
                self.test_case.assertTrue(res == "hello")

        # self.logger.debug(AsyncProxy._asyncHandlers)
        callbacks = Callbacks()
        AsyncProxy.register(callbacks)
        proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        proxy.ping_with_response(callback=callbacks.callback1)
        proxy.ping_with_response(callback=callbacks.callback2)

        while not (callbacks.called["callback1"] and callbacks.called["callback2"]):
            pass

if __name__ == "__main__":
    unittest.main()
