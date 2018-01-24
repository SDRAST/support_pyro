import threading

import Pyro4

from pyro_support import Pyro4Server, config, async_method, Pyro4PublisherServer, Pyro4Subscriber

class BasicTestZmqSubscriber(Pyro4Subscriber):

    def consume(self, data):
        self.logger.debug(data)

class BasicTestZmqPublisher(Pyro4PublisherServer):

    def __init__(self, test_case):
        Pyro4PublisherServer.__init__(self, name="BasicTestZmqPublisher")
        self.test_case = test_case

    def get_publisher_data(self):

        return {
            self.square.__name__: self.square(2),
            self.cube.__name__: self.cube(2)
        }

    def square(self, x):
        return x**2

    def cube(self, x):
        return x**3



@config.expose
class BasicTestServer(Pyro4Server):
    def __init__(self, test_case):
        Pyro4Server.__init__(self, name="BasicTestServer")
        self.test_case = test_case

    def setHandler(self,proxy):
        self.logger.debug("Setting cb_handler to {}".format(proxy))
        self.cb_handler = proxy

    @async_method
    def square(self, x):
        self.logger.debug("square: Called. Args: {}".format(x))
        self.test_case.assertIsInstance(self.square.cb, Pyro4.core._RemoteMethod)
        self.square.cb(x**2)

    @async_method
    def cube(self, x):
        self.logger.debug("cube: Called. Args: {}".format(x))
        self.test_case.assertIsInstance(self.cube.cb, Pyro4.core._RemoteMethod)
        self.cube.cb(x**3)

class BasicTestClient(object):

    def __init__(self, port, server_name, test_case, logger):

        ns = Pyro4.locateNS(port=port)
        self.server = Pyro4.Proxy(ns.lookup(server_name))
        self.test_case = test_case
        self.logger = logger

        d = Pyro4.Daemon()
        d.register(self)
        t = threading.Thread(target=d.requestLoop)
        t.daemon = True
        t.start()

    def setHandler(self):
        self.logger.debug("setHandler: Called.")
        self.server.setHandler(self)

    @config.expose
    def square_cb(self, results):
        self.logger.debug("square_cb: Called. Results: {}".format(results))
        self.test_case.assertTrue(results == 4)

    @config.expose
    def cube_cb(self, results):
        self.logger.info("cube_cb: Called. Results: {}".format(results))
        self.test_case.assertTrue(results == 8)

    @config.expose
    def process_data(self, results):
        self.logger.info("process_data: Called. Results: {}".format(results))
        self.test_case.assertIsNotNone(results)

    def test_square(self, handler=True):
        if handler:
            self.server.square(2, cb_info={"cb_handler":self,
                                           "cb":"square_cb"})
        else:
            self.server.square(2, cb_info={"cb":"square_cb"})

    def test_cube(self, handler=True):
        if handler:
            self.server.cube(2, cb_info={"cb_handler":self,
                                     "cb":"cube_cb"})
        else:
            self.server.cube(2, cb_info={"cb":"cube_cb"})
