import unittest
import threading

import Pyro4

from support_pyro.support_pyro4.async import async_method

class TestAsyncDecorator(unittest.TestCase):

    def test_async_decorator_with_function(self):

        def callback(res):
            callback.called = True

        callback.called = False

        class TestServer(object):

            @async_method
            def ping(self):
                self.ping.cb("hello")

        ts = TestServer()
        ts.ping(cb_info={"cb":callback})
        self.assertTrue(callback.called)

    def test_async_decorator_with_daemon(self):

        class CallbackServer(object):

            def __init__(self):
                self.called = {
                    "callback": False
                }

            @Pyro4.expose
            def callback(self, res):
                self.called["callback"] = True

        cbs = CallbackServer()
        daemon = Pyro4.Daemon()
        uri = daemon.register(cbs)
        t = threading.Thread(target=daemon.requestLoop)
        t.daemon = True
        t.start()

        class TestServer(object):

            @async_method
            def ping(self):
                self.ping.cb("hello")

        ts = TestServer()
        p = Pyro4.Proxy(uri)
        ts.ping(cb_info={"cb":"callback","cb_handler":p})
        self.assertTrue(cbs.called["callback"])

if __name__ == "__main__":
    unittest.main()
