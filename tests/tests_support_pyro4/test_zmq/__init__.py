import time
import random

from support_pyro.support_pyro4.zmq import ZmqPublisher, ZmqSubscriber,MultiSocketPublisherManager, SingleSocketPublisherManager
from support_pyro.support_pyro4.util import EventEmitter
from support_pyro.support_pyro4.async import async_method

class TestPublisherImplementation(ZmqPublisher):

    def publish(self):
        time.sleep(0.1)
        res = {"something random":random.random()}
        self.emitter.emit("publish",res)
        return res

    @async_method
    def start_publishing(self):
        self.emitter.emit("start")
        return super(TestPublisherImplementation, self).start_publishing()

    @async_method
    def pause_publishing(self):
        self.emitter.emit("pause")
        return super(TestPublisherImplementation, self).pause_publishing()

    @async_method
    def unpause_publishing(self):
        self.emitter.emit("unpause")
        return super(TestPublisherImplementation, self).unpause_publishing()

    @async_method
    def stop_publishing(self):
        self.emitter.emit("stop")
        return super(TestPublisherImplementation, self).stop_publishing()

def manager_factory(base_cls):
    class ManagerImplementation(base_cls):

        def __init__(self):
            super(ManagerImplementation, self).__init__(
                name=self.__class__.__name__
            )
            self.publishers = [
                TestPublisherImplementation(name="publisher{}".format(i))
                for i in xrange(4)
            ]
    @async_method
    def start_publishing(self):
        self.emitter.emit("start")
        return super(ManagerImplementation, self).start_publishing()

    @async_method
    def pause_publishing(self):
        self.emitter.emit("pause")
        return super(ManagerImplementation, self).pause_publishing()

    @async_method
    def unpause_publishing(self):
        self.emitter.emit("unpause")
        return super(ManagerImplementation, self).unpause_publishing()

    @async_method
    def stop_publishing(self):
        self.emitter.emit("stop")
        return super(ManagerImplementation, self).stop_publishing()
    return ManagerImplementation

TestMultiSocketPublisherManagerImplementation = manager_factory(MultiSocketPublisherManager)
TestSingleSocketPublisherManagerImplementation = manager_factory(SingleSocketPublisherManager)

class TestSubscriberImplementation(ZmqSubscriber):

    def consume(self, res):
        # self.emit("consume", res)
        return res
