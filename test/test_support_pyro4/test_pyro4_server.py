import unittest
import logging
import threading
import sys

import Pyro4
from Pyro4 import naming, socketutil

from .. import setup_logging
from support_pyro.support_pyro4 import Pyro4Server, config, Pyro4ServerError

class TestBasic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        host, port = "localhost", socketutil.findProbablyUnusedPort()
        uri, daemon, server = naming.startNS(host=host, port=port)
        t = threading.Thread(target=daemon.requestLoop)
        t.dameon = True
        t.start()
        cls.ns_thread = t
        cls.ns_daemon = daemon
        cls.ns_port = port
        cls.ns_host = host

    @classmethod
    def tearDownClass(cls):
        cls.ns_daemon.shutdown()
        cls.ns_thread.join()

    def setUp(self):
        self.logger = logging.getLogger("TestBasic")
        self.server = Pyro4Server()

    def test_init_name(self):
        name = "TestServer"
        server = Pyro4Server(name=name)
        self.assertTrue(server.name == name)

    def test_init_logger(self):
        server = Pyro4Server(logger=self.logger)
        self.assertTrue(server.logger.name == "TestBasic")

    def test_ping(self):
        res = self.server.ping()
        self.assertTrue(res)

    def test_raise_pyro4_server_error(self):
        def f():
            raise Pyro4ServerError("Test Exception raised")
        self.assertRaises(Pyro4ServerError, f)

    def test_launch_server(self):
        self.server.launch_server(
                                    ns_port=self.ns_port,
                                    ns_host=self.ns_host,
                                    local=True, threaded=True
        )
        self.assertTrue(self.server.running)



if __name__ == "__main__":
    setup_logging()
    logging.getLogger().info("Running support_pyro.support_pyro4.Pyro4Server basic tests")
    unittest.main()
