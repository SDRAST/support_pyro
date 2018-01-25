import sys
import inspect
import logging
import threading
import unittest

import Pyro4

from ... import setup_logging
setup_logging(logging.getLogger(), logLevel=logging.DEBUG)

from support_pyro.support_pyro4.async.async_proxy import AsyncProxy
from . import test_case_factory, SimpleServer, SimpleAsyncServer

class TestAsyncProxy(test_case_factory(SimpleServer)):

    def setUp(self):
        self.logger = logging.getLogger("TestAsyncProxy")
        self.called = {
            "callback":False
        }
        class Client(object):
            test_case = self
            called = {
                "callback": False
            }
            @Pyro4.expose
            def callback(self, res):
                self.called["callback"] = True
                self.test_case.assertTrue(res == "hello")

        def callback(res):
            self.called["callback"] = True
            self.assertTrue(res == "hello")

        self.callback = callback
        self.Client = Client
        proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        self.proxy = proxy

    def tearDown(self):
        self.proxy._daemon.shutdown()
        AsyncProxy._asyncHandlers = {}

    def test_init_full_args(self):
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000",
                                        daemon_details={"host":"localhost",
                                        "port": 50001})
        self.assertTrue(isinstance(p, AsyncProxy))
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        self.assertEqual(p._asyncHandlers, {})
        p._daemon.shutdown()

    def test_init_with_prexisting_daemon(self):
        self.proxy._daemon.shutdown()
        daemon = Pyro4.Daemon(port=50001,host="localhost")
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000",
                                            daemon_details={"daemon":daemon})
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        p._daemon.shutdown()

    def test_init_no_args(self):

        self.assertTrue("Pyro.Daemon" in self.proxy._daemon.objectsById)
        self.assertTrue("localhost" in self.proxy._daemon.locationStr)

    def test_lookup_with_function(self):
        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup(self.callback)
        self.assertTrue(obj.__class__.__name__ == self.callback.__name__)
        self.assertTrue(inspect.ismethod(obj.callback))
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

    def test_lookup_with_function_name(self):
        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup(self.callback.__name__)
        self.assertTrue(obj.__class__.__name__ == self.callback.__name__)
        self.assertTrue(inspect.ismethod(obj.callback))
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

    def test_lookup_with_obj(self):
        client = self.Client()
        self.proxy.register(client)
        obj, obj_id = self.proxy.lookup(client)
        self.assertTrue(obj is client)

    def test_register_function_with_instance_method(self):

        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup("callback")
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

    def test_register_obj_with_instance_method(self):

        client = self.Client()
        self.proxy.register(client)
        obj, obj_id = self.proxy.lookup(client)
        obj.callback("hello")
        self.assertTrue(client.called["callback"])

if __name__ == "__main__":
    unittest.main()
