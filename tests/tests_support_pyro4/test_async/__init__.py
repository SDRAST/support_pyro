import logging
import threading
import unittest

import Pyro4

from support_pyro.support_pyro4.async import async_method

module_logger = logging.getLogger(__name__)

__all__ = ["SimpleServer", "SimpleAsyncServer", "test_case_factory"]

class SimpleServer(object):

    @Pyro4.expose
    def ping(self):
        return "hello"

class SimpleAsyncServer(object):

    @async_method
    def ping_with_response(self):
        module_logger.info("ping_with_response: Called.")
        module_logger.info(
            "ping_with_response: self.ping_with_response.cb: {}".format(
                self.ping_with_response.cb
            )
        )
        self.ping_with_response.cb("hello")
