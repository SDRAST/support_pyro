import time
import logging
import threading
import unittest

import Pyro4

from ... import setup_logging
from support_pyro.support_pyro4.async.async_proxy import AsyncProxy
from . import SimpleAsyncServer
from .. import test_case_with_server

module_logger = logging.getLogger(__name__)

class TestCallbackIntegration(test_case_with_server(SimpleAsyncServer)):

    def setUp(self):
        self.logger = logging.getLogger("TestCallbackIntegration")
        self.proxy = AsyncProxy(self.uri)

    def tearDown(self):
        self.proxy.shutdown()
        AsyncProxy._asyncHandlers = {}

    def test_callback_integration_force_register_function(self):
        called = {
            "handler":False
        }
        def handler(res):
            self.logger.debug("handler: res: {}".format(res))
            called["handler"] = True
            self.assertTrue(res == "hello")

        self.proxy.ping_with_response(callback=handler)
        while not called["handler"]:
            pass
        called["handler"] = False
        self.proxy.shutdown()

        self.proxy = AsyncProxy(self.uri)
        self.proxy.ping_with_response(callback=handler)
        while not called["handler"]:
            pass

    def test_callback_integration_preregister_function(self):
        called = {
            "handler":False
        }

        def handler(res):
            self.logger.debug("handler: res: {}".format(res))
            called["handler"] = True
            self.assertTrue(res == "hello")

        self.proxy.register(handler)
        self.proxy.ping_with_response(callback=handler)
        while not called["handler"]:
            pass

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

        self.proxy.ping_with_response(callback=callback)
        self.proxy.ping_with_response(callback=handler)

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

        callbacks = Callbacks()
        proxy = AsyncProxy(self.uri)
        proxy.ping_with_response(callback=callbacks.callback1)
        proxy.ping_with_response(callback=callbacks.callback2)

        while not (callbacks.called["callback1"] and callbacks.called["callback2"]):
            pass

    def test_callback_integration_no_callback(self):
        proxy = AsyncProxy(self.uri)
        proxy.ping_with_response()


if __name__ == "__main__":
    setup_logging(logLevel=logging.DEBUG)
    unittest.main()
