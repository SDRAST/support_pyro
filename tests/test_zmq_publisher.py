import unittest
import sys
import time
import logging
import threading
import random

import pyro4tunneling

import Pyro4
import Pyro4.naming
import Pyro4.socketutil

# from pyro_support.pyro4_publisher import PublisherThread

from . import BasicTestZmqPublisher, BasicTestClient

class TestZmqPublisherBackend(unittest.TestCase):

    __isSetup__ = False

    def setUp(self):

        if not self.__class__.__isSetup__:
            port = Pyro4.socketutil.findProbablyUnusedPort()
            ns_details = Pyro4.naming.startNS(port=port)
            ns_thread = threading.Thread(target=ns_details[1].requestLoop)
            ns_thread.daemon = True
            ns_thread.start()

            res = pyro4tunneling.util.check_connection(Pyro4.locateNS, kwargs={"port":port})

            server = BasicTestZmqPublisher(self)
            bs_thread = server.launch_server(ns_port=port, local=True, threaded=True)

            self.__class__.server = server
            self.__class__.port = port

            self.__class__.__isSetup__ = True
        else:
            pass

    def test_start_pause_stop(self):

        logger = logging.getLogger("TestZmqPublisherBackend.test_basic_publisher")
        server = self.__class__.server
        # client = BasicTestClient(self.__class__.port, "BasicTestZmqPublisher", self, logger)
        server.start_publishing(0.1)
        time.sleep(1.0)
        server.pause_publishing()
        time.sleep(1.0)
        server.unpause_publishing()
        time.sleep(1.0)
        server.stop_publishing()



    @unittest.skip("")
    def test_multiple_subscribers(self):

        logger = logging.getLogger("TestPublisherThread.test_multiple_subscribers")

        def data_function():
            return random.random()

        def process_data2(results):
            logger.debug("process_data2: Called. Results: {}".format(results))
            self.assertIsNotNone(results)

        client = BasicTestClient(self.port, "BasicServer", self, logger)

        publisher = PublisherThread(0.2, data_function, cb_info={
            "cb_handler": client,
            "cb": "process_data"
        })
        publisher.start()
        time.sleep(0.5)
        publisher.pause_thread()
        publisher.register_callback({"cb":process_data2})
        publisher.unpause_thread()
        time.sleep(0.5)
        publisher.stop_thread()

    @unittest.skip("")
    def test_adjust_rate(self):

        logger = logging.getLogger("TestPublisherThread.test_adjust_rate")

        def data_function():
            return random.random()

        def process_data2(results):
            logger.debug("process_data2: Called. Results: {}".format(results))
            self.assertIsNotNone(results)

        client = BasicTestClient(self.port, "BasicServer", self, logger)

        publisher = PublisherThread(0.2, data_function, cb_info={
            "cb": process_data2
        })
        new_rate = 0.01
        publisher.start()
        time.sleep(0.5)
        publisher.pause_thread()
        publisher.change_rate(new_rate)
        publisher.unpause_thread()
        time.sleep(0.3)
        publisher.stop_thread()
        self.assertTrue(publisher.update_rate == new_rate)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    unittest.main()
