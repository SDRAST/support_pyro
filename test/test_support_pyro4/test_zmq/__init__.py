import time
import random

from support_pyro.support_pyro4.zmq import Publisher, Subscriber
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

class TestSubscriberImplementation(Subscriber):

    def consume(self, res):
        print(res)
