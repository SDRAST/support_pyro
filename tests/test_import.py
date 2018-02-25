import unittest

class TestImport(unittest.TestCase):

    def test_import_zmq(self):
        from support_pyro.support_pyro4.zmq import Publisher, Subscriber

    def test_import_async(self):
        from support_pyro.support_pyro4.async import CallbackProxy, async_method, async_callback, AsyncProxy

    def test_import_support_pyro4(self):
        from support_pyro.support_pyro4 import Pyro4Server, Pyro4Client, AutoReconnectingProxy, config

    def test_import_support_pyro3(self):
        import support_pyro.support_pyro3 as p
        self.assertTrue(callable(p.get_device_server))

    def test_import_get_device_server(self):
        from support_pyro import get_device_server

if __name__ == "__main__":
    unittest.main()
