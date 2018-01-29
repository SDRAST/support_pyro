import sys
import logging

import zmq
import Pyro4

from ..async import async_callback
from ..async.async_proxy import AsyncProxy
from ..util import iterative_run, PausableThread, EventEmitter

__all__ = ["Subscriber"]

module_logger = logging.getLogger(__name__)

class SubscriberThread(PausableThread):

    def __init__(self, context, serializer, host="localhost", port=0, **kwargs):
        super(SubscriberThread, self).__init__(**kwargs)
        self.context = context
        self.serializer = serializer
        self.host = host
        if port == 0:
            port = Pyro4.socketutil.findProbablyUnusedPort()
        self.port = port
        self.address = "tcp://{}:{}".format(host, port)
        if sys.version_info[0] == 2:
            callback = self._Thread__target
        else:
            callback = self._target
        self.callback = callback
        self.logger.debug("__init__: creating socket and connecting to address: {}".format(self.address))
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,"")
        self.socket.connect(self.address)

    @iterative_run
    def run(self):
        if not self.socket.closed:
            self.logger.debug("run: calling socket.recv")
            res = self.socket.recv()
            self.logger.debug("run: got {} from socket".format(res))
            self.callback(res)

class Subscriber(object):

    def __init__(self, uri, logger=None):
        self.proxy = AsyncProxy(uri)
        self.proxy.register(self)
        self.context = zmq.Context.instance()
        self.subscriber_thread = None
        self.subscribing_started = False
        self.subscribing_stopped = True
        self.subscribing_paused = False
        self.serializer_name = self.proxy.serializer_name
        self.serializer = self.proxy.serializer
        self.emitter = EventEmitter()
        if logger is None: logger = logging.getLogger(module_logger.name+".Subscriber")
        self.logger = logger

    def __getattr__(self, attr):
        return getattr(self.proxy, attr)

    @async_callback
    def start_subscribing(self,res=None):
        self.logger.debug("start_subscribing: called.")
        def subscriber_thread_factory(address):
            self.logger.debug("start_subscribing.subscriber_thread_factory: address {}".format(address))
            host, port = address.split(":")
            if host == "*":
                host = "localhost"
            subscriber_thread = SubscriberThread(
                self.context,self.serializer,
                target=self._consume_msg,host=host, port=port
            )
            self.subscribing_started = True
            subscriber_thread.start()
            return subscriber_thread

        if res is not None:
            self.emitter.emit("start")
            self.logger.debug("start_subscribing: res: {}".format(res))
            address = res["address"]
            if self.subscribing_started:
                return
            elif self.subscribing_paused:
                self.unpause_subscribing()
            elif self.subscribing_stopped:
                self.subscriber_thread = subscriber_thread_factory(address)
        else:
            self.proxy.start_publishing(callback=self.start_subscribing)

    def pause_subscribing(self):
        self.logger.debug("pause_subscribing: called.")
        self.emitter.emit("pause")
        if self.subscriber_thread is not None:
            self.subscribing_paused = True
            self.subscriber_thread.pause()

    def unpause_subscribing(self):
        self.logger.debug("unpause_subscribing: called.")
        self.emitter.emit("unpause")
        if self.subscriber_thread is not None:
            self.subscribing_paused = False
            self.subscriber_thread.unpause()

    def stop_subscribing(self):
        self.logger.debug("stop_subscribing: called.")
        self.subscribing_stopped = True
        self.subscribing_started = False
        self.emitter.emit("stop")
        if self.subscriber_thread is not None:
            self.subscriber_thread.stop()
            self.subscriber_thread.join()
            self.subscriber_thread = None

    def _consume_msg(self, msg):
        """Deserialize the message from server and ship off to self.consume"""
        res = self.serializer.loads(msg)
        self.emitter.emit("consume", res)
        self.consume(res)
        return res

    def consume(self, res):
        """Meant to be reimplemented in child subclass"""
        raise NotImplementedError
