import unittest
import time
import logging
import threading
import sys

import Pyro4
from Pyro4 import naming, socketutil

from .. import setup_logging
from support_pyro.support_pyro4 import Pyro4Server
from support.trifeni import errors

class TestClass(object):

    def __init__(self, some_arg, some_kwarg=None):
        pass

    def square(self, x):
        return x**2

class TestPyro4Server(unittest.TestCase):

    def test_as_decorator(self):

        @Pyro4Server
        class TestClass1(object):
            def square(self, x): return x**2

        server, obj = TestClass1()
        self.assertTrue(obj.square(10) == 100)

    # @unittest.skip("")
    def test_init_with_obj(self):
        obj = TestClass("hello")
        server = Pyro4Server(obj=obj)
        self.assertTrue(isinstance(server.obj, TestClass))

    # @unittest.skip("")
    def test_init_with_cls(self):
        server = Pyro4Server(cls=TestClass,
                             cls_args=("hello",),
                             cls_kwargs={"some_kwarg":"also hello"})
        self.assertTrue(isinstance(server.obj, TestClass))

    # @unittest.skip("")
    def test_init_no_cls_no_obj(self):
        with self.assertRaises(RuntimeError):
            Pyro4Server()

    # @unittest.skip("")
    def test_launch_server_local_no_ns(self):
        obj = TestClass("hello")
        server = Pyro4Server(obj=obj)
        server.launch_server(tunnel_kwargs={"local":True},
                            threaded=True,
                            ns=False,objectId="TestClass",objectPort=0)

    # @unittest.skip("")
    def test_launch_server_local_with_ns(self):
        ns_uri, ns_daemon, ns = Pyro4.naming.startNS()
        t = threading.Thread(target=ns_daemon.requestLoop)
        t.daemon = True
        t.start()
        time.sleep(1)
        obj = TestClass("hello")
        server = Pyro4Server(obj=obj)
        server.launch_server(tunnel_kwargs={"local":True,"ns_port":9090,"ns_host":"localhost"},
                            threaded=True,ns=True,objectId="TestClass",objectPort=0)
        ns_daemon.shutdown()

# @unittest.skip("")
class TestPyro4ServerIntegration(unittest.TestCase):
    """
    Assumes there is a SSH alias "me" setup.
    """
    @classmethod
    def setUpClass(cls):
        ns_uri, ns_daemon, ns = Pyro4.naming.startNS()
        t = threading.Thread(target=ns_daemon.requestLoop)
        t.daemon = True
        t.start()
        cls.ns_daemon = ns_daemon

    @classmethod
    def tearDownClass(cls):
        cls.ns_daemon.shutdown()

    def test_launch_server_no_ns(self):
        obj = TestClass("hello")
        server = Pyro4Server(obj=obj)
        with self.assertRaises(errors.TunnelError):
            server.launch_server(tunnel_kwargs={"remote_server_name":"me"},
                                 threaded=True,ns=False)

    def test_launch_server_with_ns(self):
        obj = TestClass("hello")
        server = Pyro4Server(obj=obj)
        with self.assertRaises(errors.TunnelError):
            server = server.launch_server(
                                tunnel_kwargs={"remote_server_name":"me","ns_host":"localhost","ns_port":9090},
                                 threaded=True,ns=True)

if __name__ == "__main__":
    setup_logging()
    unittest.main()
