import sys
import inspect
import logging
import threading
import unittest

import Pyro4

from support.logs import setup_logging

from support_pyro.support_pyro4.async import async_callback
from support_pyro.support_pyro4.async.async_proxy import AsyncProxy
from support_pyro.support_pyro4.async.async_client import AsyncClient

from . import SimpleServer, SimpleAsyncServer
from .. import test_case_with_server

class TestAsyncProxy(test_case_with_server(SimpleServer)):

    def setUp(self):
        self.logger = logging.getLogger("TestAsyncProxy")
        self.called = {
            "callback":False
        }

        class Client(AsyncClient):

            test_case = self

            @async_callback
            def callback(self, res):
                self.test_case.assertTrue(res == "hello")

        def callback(res):
            self.called["callback"] = True
            self.assertTrue(res == "hello")
            return res

        self.callback = callback
        self.Client = Client
        proxy = AsyncProxy(self.uri)
        self.proxy = proxy

    def tearDown(self):
        self.proxy._daemon.shutdown()
        AsyncProxy._asyncHandlers = {}

#    @unittest.skip("")
    def test_init_full_args(self):
        p = AsyncProxy(self.uri,
                        daemon_details={"host":"localhost",
                        "port": 50001})
        self.assertTrue(isinstance(p, AsyncProxy))
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        self.assertEqual(p._asyncHandlers, {})
        p._daemon.shutdown()

#    @unittest.skip("")
    def test_init_with_prexisting_daemon(self):
        self.proxy._daemon.shutdown()
        daemon = Pyro4.Daemon(port=50001,host="localhost")
        p = AsyncProxy(self.uri,daemon_details={"daemon":daemon})
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        p._daemon.shutdown()

#    @unittest.skip("")
    def test_init_no_args(self):

        self.assertTrue("Pyro.Daemon" in self.proxy._daemon.objectsById)
        self.assertTrue("localhost" in self.proxy._daemon.locationStr)

#    @unittest.skip("")
    def test_lookup_with_function(self):
        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup(self.callback)[0]
        self.assertTrue(obj.__class__.__name__ == self.callback.__name__)
        self.assertTrue(inspect.ismethod(obj.callback))
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

#    @unittest.skip("")
    def test_lookup_with_function_name(self):
        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup(self.callback.__name__)[0]
        self.assertTrue(obj.__class__.__name__ == self.callback.__name__)
        self.assertTrue(inspect.ismethod(obj.callback))
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

#    @unittest.skip("")
    def test_lookup_with_obj(self):
        client = self.Client()
        self.proxy.register(client)
        obj, obj_id = self.proxy.lookup(client)[0]
        self.assertTrue(obj is client)

#    @unittest.skip("")
    def test_register_function(self):

        self.proxy.register(self.callback)
        obj, obj_id = self.proxy.lookup("callback")[0]
        obj.callback("hello")
        self.assertTrue(self.called["callback"])

#    @unittest.skip("")
    def test_register_obj_with(self):

        client = self.Client()
        self.proxy.register(client)
        obj, obj_id = self.proxy.lookup(client)[0]
        obj.callback("hello")
        self.assertTrue(client._called["callback"])

#    @unittest.skip("")
    def test_register_multiple_obj(self):
        client = self.Client()
        callback = self.callback
        self.proxy.register(client, callback)
        obj, objectId = self.proxy.lookup(client)[0]
        obj.callback("hello")
        self.assertTrue(client._called["callback"])

        obj, objectId = self.proxy.lookup(callback)[0]
        obj.callback("hello")
        self.assertTrue(self.called["callback"])
        # obj, objectId = self.proxy.lookup(client)[0]
        # print(obj)

#    @unittest.skip("")
    def test_register_handlers_with_daemon(self):
        callback = self.callback
        self.proxy.register(callback)
        self.proxy.register_handlers_with_daemon()
        obj, objectId = self.proxy.lookup(callback)[0]
        self.assertTrue(objectId in self.proxy._asyncHandlers)
        self.assertTrue(objectId in self.proxy._daemon.objectsById)

#    @unittest.skip("")
    def test_unregister_obj(self):
        client = self.Client()
        self.proxy.register(client)
        self.proxy.unregister(client)
        self.assertTrue(self.proxy._asyncHandlers == {})

#    @unittest.skip("")
    def test_unregister_obj_from_daemon(self):
        client = self.Client()
        self.proxy.register(client)
        self.proxy.register_handlers_with_daemon()
        self.proxy.unregister(client)
        self.assertTrue(self.proxy._asyncHandlers == {})
        self.assertTrue(self.proxy._daemon.objectsById.keys() == ["Pyro.Daemon"])

#    @unittest.skip("")
    def test_create_handler_class(self):
        def fn(x, y):
            return x, y
        handler = AsyncProxy.create_handler_class(fn)
        handler_obj = handler()
        res = handler_obj.fn(5,6)
        self.assertTrue(handler.__name__ == fn.__name__)
        self.assertTrue(res == (5,6))

#    @unittest.skip("")
    def test_lookup_function_or_method(self):

        self.proxy.register(self.callback)
        res = self.proxy.lookup_function_or_method(self.callback)
        self.assertTrue(res["method"] == self.callback.__name__)

#    @unittest.skip("")
    def test_wait_fn(self):
        self.proxy.register(self.callback)
        obj, _ = self.proxy.lookup(self.callback)[0]
        with self.proxy.wait(self.callback):
            obj.callback("hello")
        # res = self.proxy.wait(self.callback)
        # self.assertTrue(res == "hello")

#    @unittest.skip("")
    def test_wait_obj(self):
        client = self.Client()
        self.proxy.register(client)
        obj, _ = self.proxy.lookup(client)[0]
        with self.proxy.wait(client.callback):
            obj.callback("hello")

if __name__ == "__main__":
    setup_logging(logLevel=logging.INFO)
    unittest.main()
