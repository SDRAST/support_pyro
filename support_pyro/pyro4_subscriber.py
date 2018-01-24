from __future__ import print_function
import time
import logging

import zmq
import serpent
import Pyro4

from .pyro4_client import Pyro4Client
from .util import PausableThread, iterative_run

__all__ = ["ZmqSubscriberThread", "Pyro4Subscriber"]

class ZmqSubscriberThread(PausableThread):

    def __init__(self, consume_cb, context,address,
                    topic="",
                    consume_cb_args=None,
                    consume_cb_kwargs=None,
                    serializer="serpent",
                    **kwargs):

        PausableThread.__init__(self, **kwargs)
        self.consume_cb = consume_cb
        self.topic = topic
        self.socket = context.socket(zmq.SUB)
        self.socket.connect(address)
        self.socket.setsockopt(zmq.SUBSCRIBE, self.topic)
        if consume_cb_args is None: self.consume_cb_args = ()
        if consume_cb_kwargs is None: self.consume_cb_kwargs = {}
        if serializer == "serpent":
            self.serializer = serpent
        elif serializer == "json":
            self.serializer = json
        else:
            raise Pyro4ServerError("Don't recognize serializer {}".format(serializer))

    @iterative_run
    def run(self):
        data = self.serializer.loads(self.socket.recv())
        self.consume_cb(data, *self.consume_cb_args, **self.consume_cb_kwargs)

    def stop_thread(self):
        super(ZmqSubscriberThread, self).stop_thread()
        self.socket.close()

class Pyro4Subscriber(Pyro4Client):

    backend = "zmq"

    def __init__(self, *args, **kwargs):
        Pyro4Client.__init__(self, *args, **kwargs)
        self.subscriber_thread = None
        self.context = None
        self.subscriber_address = None

    def consume(self, data):
        raise NotImplementedError("Subclass should reimplement this")

    def start_subscribing(self):

        if self.backend == "zmq":
            context = zmq.Context()
            address = self.server.publisher_address
            if ("*" in address):
                address = address.replace("*","localhost")
            self.logger.debug("Starting subscribing at {}".format(address))
            self.subscriber_address = address
            self.context = context
            self.subscriber_thread = ZmqSubscriberThread(self.consume, context, address)
            self.subscriber_thread.start()
        else:
            raise Pyro4ServerError("`start_subscribing` not implemented for backend \"{}\"".format(self.backend))

    def pause_subscribing(self):

        self.logger.debug("Pausing subscribing")
        if self.subscriber_thread is None:
            self.logger.debug("No subscriber thread to unpause")
        else:
            self.subscriber_thread.pause_thread()

    def unpause_subscribing(self):

        self.logger.debug("Unpausing subscribing")
        if self.subscriber_thread is None:
            self.logger.debug("No subscriber thread to unpause")
        else:
            self.subscriber_thread.unpause_thread()

    def stop_subscribing(self):

        self.logger.debug("Stopping subscribing")
        if self.subscriber_thread is None:
            self.logger.debug("No subscriber thread to unpause")
        else:
            self.subscriber_thread.pause_thread()
            self.subscriber_thread.stop_thread()
            self.subscriber_thread = None
