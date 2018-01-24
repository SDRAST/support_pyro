import threading
import unittest

import Pyro4

from src.async_proxy import AsyncProxy
from . import test_case_factory, SimpleServer, SimpleAsyncServer

class TestAsyncProxy(test_case_factory(SimpleServer)):

    def test_init_full_args(self):
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000",
                                        daemon_details={"host":"localhost",
                                        "port": 50001,
                                        "objectId":"AsyncCallbacks"})
        self.assertTrue(isinstance(p, AsyncProxy))
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        self.assertTrue("AsyncCallbacks" in p._daemon.objectsById)
        p._daemon.shutdown()

    def test_init_with_prexisting_daemon(self):

        daemon = Pyro4.Daemon(port=50001,host="localhost")
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000",
                                            daemon_details={"daemon":daemon})
        self.assertTrue(p._daemon.locationStr == "localhost:50001")
        p._daemon.shutdown()

    def test_init_no_args(self):

        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        self.assertTrue("Pyro.Daemon" in p._daemon.objectsById)
        self.assertTrue("localhost" in p._daemon.locationStr)
        p._daemon.shutdown()

    def test_register_as_class_method(self):

        def callback(res):
            self.assertTrue(res=="hello")

        AsyncProxy.register(callback)
        self.assertTrue(callback.__name__ in AsyncProxy.Handler.__dict__)
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        p._asyncHandler.callback("hello")
        p._daemon.shutdown()

    def test_register_as_instance_method(self):

        class Client(object):

            test_case = self

            @Pyro4.expose
            def callback(self, res):
                self.test_case.assertTrue(res == "hello")

        client = Client()
        p = AsyncProxy("PYRO:SimpleAsyncServer@localhost:50000")
        p.register(client)
        p._asyncHandler.callback("hello")
        p._daemon.shutdown()

if __name__ == "__main__":
    unittest.main()
