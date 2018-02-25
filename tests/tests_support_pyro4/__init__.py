import unittest
import threading

import Pyro4

def test_case_with_server(server_class, *args, **kwargs):

    class TestCaseWithServer(unittest.TestCase):

        @classmethod
        def setUpClass(cls):
            server = server_class(*args, **kwargs)
            daemon = Pyro4.Daemon(port=0, host="localhost")
            uri = daemon.register(server, objectId=server_class.__name__)
            daemon_thread = threading.Thread(target=daemon.requestLoop)
            daemon_thread.daemon = True
            daemon_thread.start()

            cls.uri = uri
            cls.server = server
            cls.daemon = daemon
            cls.daemon_thread = daemon_thread

        @classmethod
        def tearDownClass(cls):
            cls.daemon.shutdown()
            cls.daemon_thread.join()

    return TestCaseWithServer
