import time
import random

from support_pyro.support_pyro4.zmq import ZmqPublisher, ZmqSubscriber
from support_pyro.support_pyro4.util import EventEmitter
from support_pyro.support_pyro4.async import async_method

class TestPublisherImplementation(ZmqPublisher):

    # def __init__(self,*args, **kwargs):
    #     super(TestPublisherImplementation, self).__init__(*args, **kwargs)

    def publish(self):
        time.sleep(1.0)
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


class TestSubscriberImplementation(ZmqSubscriber):

    def consume(self, res):
        # self.emit("consume", res)
        return res
