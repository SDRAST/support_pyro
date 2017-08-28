import unittest
import sys
import threading
import logging

import Pyro4
import Pyro4.naming
import Pyro4.socketutil

import pyro4tunneling

from pyro_support.util import async_method
from pyro_support import Pyro4Server, config

from . import BasicTestClient, BasicTestServer

class TestAsyncMethodDecorator(unittest.TestCase):

    __isSetup__ = False

    def setUp(self):

        if not self.__isSetup__:
            self.__isSetup__ = True
            self.port = Pyro4.socketutil.findProbablyUnusedPort()
            ns_details = Pyro4.naming.startNS(port=self.port)
            self.ns_thread = threading.Thread(target=ns_details[1].requestLoop)
            # self.ns_thread = threading.Thread(target=Pyro4.naming.startNSloop,
            #                                 kwargs={"port":self.port})
            self.ns_thread.daemon = True
            self.ns_thread.start()

            res = pyro4tunneling.util.check_connection(Pyro4.locateNS, kwargs={"port":self.port})

            self.server = BasicTestServer(self)
            self.bs_thread = self.server.launch_server(ns_port=self.port, local=True, threaded=True)
        elif self.__isSetup__:
            pass

    def test_pyro4_cb_with_handler(self):
        """
        """
        logger = logging.getLogger("TestAsyncMethodDecorator.test_pyro4_cb_with_handler")
        client = BasicTestClient(self.port, "BasicServer", self, logger)
        client.test_square(handler=True)
        client.test_cube(handler=True)

    def test_pyro4_cb_no_handler(self):
        """
        Test calling client side callbacks in the case where we don't send cb_handler info.
        """
        logger = logging.getLogger("TestAsyncMethodDecorator.test_pyro4_cb_no_handler")
        client = BasicTestClient(self.port, "BasicServer", self, logger)
        client.setHandler()
        client.test_square(handler=False)
        client.test_cube(handler=False)

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    unittest.main()
