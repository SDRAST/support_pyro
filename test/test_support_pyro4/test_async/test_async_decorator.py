import unittest

import Pyro4

from src import async

class TestAsyncDecorator(unittest.TestCase):

    def test_async_decorator_with_function(self):

        def callback(res):
            callback.called = True
            # print("callback: res: {}".format(res))

        callback.called = False

        class TestServer(object):

            @async
            def ping(self):
                self.ping.callback("hello")

        ts = TestServer()
        ts.ping(callback=callback)
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
        daemon.register(cbs)

        class TestServer(object):

            @async
            def ping(self):
                self.ping.callback("hello")

        ts = TestServer()
        ts.ping(callback={"callback":"callback","handler":cbs})
        self.assertTrue(cbs.called["callback"])
