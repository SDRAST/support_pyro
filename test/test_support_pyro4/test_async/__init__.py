import logging
import threading
import unittest

import Pyro4
# from ... import setup_logging
# setup_logging(logLevel=logging.DEBUG)

from support_pyro.support_pyro4 import async

module_logger = logging.getLogger(__name__)
module_logger.debug("from __init__")

# print("available loggers: {}".format(logging.Logger.manager.loggerDict))
# print(logging.getLogger("support_pyro.support_pyro4.async").handlers)
# print(logging.getLogger("support_pyro.support_pyro4.async.async_proxy").handlers)

class SimpleServer(object):

    @Pyro4.expose
    def ping(self):
        return "hello"

class SimpleAsyncServer(object):

    # @Pyro4.expose
    @async
    def ping_with_response(self):
        module_logger.info("ping_with_response: Called.")
        module_logger.info(
            "ping_with_response: self.ping_with_response.cb: {}".format(
                self.ping_with_response.cb
            )
        )
        self.ping_with_response.cb("hello")


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
