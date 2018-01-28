import time
import random

from support_pyro.support_pyro4.zmq import Publisher
from support_pyro.support_pyro4.util import EventEmitter

class TestPublisherImplementation(Publisher):

    def __init__(self,*args, **kwargs):
        super(TestPublisherImplementation, self).__init__(*args, **kwargs)
        self.event_emitter = EventEmitter()

    def publish(self):
        time.sleep(0.1)
        res = {"something random":random.random()}
        self.event_emitter.emit("publish",res)
        return res

    def pause_publishing(self):
        super(TestPublisherImplementation, self).pause_publishing()
        self.event_emitter.emit("pause")

    def unpause_publishing(self):
        super(TestPublisherImplementation, self).unpause_publishing()
        self.event_emitter.emit("unpause")

    def stop_publishing(self):
        super(TestPublisherImplementation, self).stop_publishing()
        self.event_emitter.emit("stop")
