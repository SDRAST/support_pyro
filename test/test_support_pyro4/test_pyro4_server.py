import unittest
import logging
import sys

from pyro_support.util import AsyncCallback
from pyro_support import Pyro4Server, config, Pyro4ServerError

class TestBasic(unittest.TestCase):

    def test_init_server(self):

        name = "TestServer"
        server = Pyro4Server(name=name)
        self.assertTrue(server.name == name)

    def test_raise_pyro4_server_error(self):

        def f():
            raise Pyro4ServerError("Test Exception raised")

        self.assertRaises(Pyro4ServerError, f)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    logging.info("Running pyro4-support basic test")
    unittest.main()
