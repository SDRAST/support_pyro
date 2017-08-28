import unittest
import types
import threading

import Pyro4
import Pyro4.naming
import Pyro4.socketutil

import pyro4tunneling

from pyro_support.util import AsyncCallback
from pyro_support import Pyro4Server, config

class TestAsyncCallback(unittest.TestCase):


    def test_function_str_name_cb(self):
        """
        Make sure that if we pass the name of a function with no cb_handler,
        we get an error
        """
        def square(x):
            return x**2

        with self.assertRaises(RuntimeError):
            AsyncCallback(cb_info={"cb":"square"})

    def test_function_cb(self):
        """
        Test whether we can create an AsyncCallback object with a simple function
        """
        def square(x):
            return x**2

        def cube(x):
            return x**3

        async_cb = AsyncCallback(cb_info={"cb":square, "cb_updates":cube})
        self.assertIsInstance(async_cb.cb, types.FunctionType)
        self.assertIsInstance(async_cb.cb_updates, types.FunctionType)
        async_cb = AsyncCallback(cb_info={"cb":square})
        self.assertIsInstance(async_cb.cb, types.FunctionType)
        async_cb = AsyncCallback(cb_info={"cb_updates":cube})
        self.assertIsInstance(async_cb.cb_updates, types.FunctionType)

    def test_instance_method_cb(self):
        """
        Test whether we can create an AsyncCallback object with an instance method.
        """
        class TestClass(object):
            def square(self, x):
                return x**2
            def cube(self, x):
                return x**3

        test_object = TestClass()
        async_cb = AsyncCallback(cb_info={"cb":test_object.square, "cb_updates":test_object.cube})
        self.assertIsInstance(async_cb.cb, types.MethodType)
        self.assertIsInstance(async_cb.cb_updates, types.MethodType)
        async_cb = AsyncCallback(cb_info={"cb":test_object.square})
        self.assertIsInstance(async_cb.cb, types.MethodType)
        async_cb = AsyncCallback(cb_info={"cb_updates":test_object.cube})
        self.assertIsInstance(async_cb.cb_updates, types.MethodType)

    def test_socket_cb(self):
        """
        Test whether or not we can use the flask_socketio callback registration.
        """
        class BasicServer(Pyro4Server):
            def square(self, x):
                return x**2
            def cube(self, x):
                return x**3

        app, socketio, server = BasicServer.flaskify_io()

        async_cb = AsyncCallback(cb_info={"cb":"cb", "cb_updates":"cb_updates"},
                                 socket_info={"app":app, "socketio": socketio})

        self.assertTrue(async_cb.cb.__name__=="emit_f")

    def test_pyro4_cb(self):
        """
        Test whether or not we can register Pyro client methods with an async callback
        """
        @config.expose
        class BasicServer(Pyro4Server):

            def __init__(self):
                Pyro4Server.__init__(self, name="BasicServer")
            def square(self, x):
                return x**2
            def cube(self, x):
                return x**3

        port = Pyro4.socketutil.findProbablyUnusedPort()
        ns_details = Pyro4.naming.startNS(port=port)
        self.ns_thread = threading.Thread(target=ns_details[1].requestLoop)
        # self.ns_thread = threading.Thread(target=Pyro4.naming.startNSloop,
        #                                 kwargs={"port":port})
        self.ns_thread.daemon = True
        self.ns_thread.start()

        res = pyro4tunneling.util.check_connection(Pyro4.locateNS, kwargs={"port":port})

        server = BasicServer()
        self.bs_thread = server.launch_server(ns_port=port, local=True, threaded=True)

        ns = Pyro4.locateNS(port=port)
        bs_proxy = Pyro4.Proxy(ns.lookup("BasicServer"))

        async_cb = AsyncCallback(cb_info={"cb_handler":bs_proxy,
                                          "cb":"square",
                                          "cb_updates":"cube"})

        self.assertIsInstance(async_cb.cb, Pyro4.core._RemoteMethod)
        self.assertIsInstance(async_cb.cb_updates, Pyro4.core._RemoteMethod)
        self.assertTrue(async_cb.cb(2) == 4)
        self.assertTrue(async_cb.cb_updates(2) == 8)

if __name__ == "__main__":
    unittest.main()
