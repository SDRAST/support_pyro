import threading
import unittest

import Pyro4

from src import async

class SimpleServer(object):

    @Pyro4.expose
    def ping(self):
        return "hello"

class SimpleAsyncServer(object):

    @async
    def ping_with_response(self):
        print("ping_with_response: Called.")
        self.ping_with_response.callback("hello")


def test_case_factory(server_cls):
    class TestCaseWithServer(unittest.TestCase):

        @classmethod
        def setUpClass(cls):

            s = server_cls()
            d = Pyro4.Daemon(host="localhost",port=50000)
            d.register(s,objectId="SimpleAsyncServer")
            t = threading.Thread(target=d.requestLoop)
            t.daemon = True
            t.start()
            cls.daemon = d
            cls.daemon_thread = t

        @classmethod
        def tearDownClass(cls):

            cls.daemon.shutdown()
            cls.daemon_thread.join()

    return TestCaseWithServer
