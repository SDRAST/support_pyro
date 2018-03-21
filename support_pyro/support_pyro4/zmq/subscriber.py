import sys
import logging

import zmq
import Pyro4

from ..async import async_callback
from ..async.async_proxy import AsyncProxy
from ..util import iterative_run, PausableThread, EventEmitter

__all__ = ["ZmqSubscriber"]

module_logger = logging.getLogger(__name__)

class SubscriberThread(PausableThread):
    """
    Thread for consuming incoming messages from a remote publisher.
    Attributes:
        context (zmq.Context.instance): zmq context
        serializer (serializer like object): object with `loads` method
        host (str): zmq socket host
        port (port): zmq socket port
        address (str): zmq subscribing address
        callback (callable): thread's target
        socket (zmq.Socket): zmq Socket instance.
    """
    def __init__(self, context, serializer, host="localhost", port=0, **kwargs):
        """
        Args:
            context (zmq.Context.instance): zmq context
            serializer (serializer like object): object with `loads` method
            kwargs (dict): passed to super class
        Keyword Args:
            host (str): zmq socket host. ("localhost")
            port (port): zmq socket port. (0)
        """
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
            # self.logger.debug("run: calling socket.recv")
            res = self.serializer.loads(self.socket.recv())
            # self.logger.debug("run: got {} from socket".format(res))
            self.callback(res)

class Subscriber(EventEmitter):
    """
    Subscriber base class. This is meant to be subclassed, and the consume
    method reimplemented.

    Attributes:
        subscriber_thread (thread like object)
        subscribing_started (bool): boolean indicating whether subscriber has started
        subscribing_stopped (bool): boolean indicating whether subscriber is stopped
        subscribing_paused (bool): boolean indicating whether subscriber is paused
        logger (logging.getLogger): logging instance

    """
    def __init__(self, logger=None):
        """
        Keyword Arguments:
            logger (logging.getLogger): logging instance.
        """
        super(Subscriber, self).__init__()
        self.subscriber_thread = None
        self.subscribing_started = False
        self.subscribing_stopped = True
        self.subscribing_paused = False
        if logger is None: logger = logging.getLogger(module_logger.name+".Subscriber")
        self.logger = logger

    def start_subscribing(self):
        self.logger.debug("start_subscribing: called.")
        self.emit("start")

    def pause_subscribing(self):
        self.logger.debug("pause_subscribing: called.")
        self.emit("pause")
        if self.subscriber_thread is not None:
            self.subscribing_paused = True
            if isinstance(self.subscriber_thread, dict):
                for name in self.subscriber_thread:
                    self.subscriber_thread[name].pause()
            else:
                self.subscriber_thread.pause()

    def unpause_subscribing(self):
        self.logger.debug("unpause_subscribing: called.")
        self.emit("unpause")
        if self.subscriber_thread is not None:
            self.subscribing_paused = False
            if isinstance(self.subscriber_thread, dict):
                for name in self.subscriber_thread:
                    self.subscriber_thread[name].unpause()
            else:
                self.subscriber_thread.unpause()

    def stop_subscribing(self):
        self.logger.debug("stop_subscribing: called.")
        self.subscribing_stopped = True
        self.subscribing_started = False
        self.emit("stop")
        if self.subscriber_thread is not None:
            if isinstance(self.subscriber_thread, dict):
                for name in self.subscriber_thread:
                    self.subscriber_thread[name].stop()
                    self.subscriber_thread[name].join()
            else:
                self.subscriber_thread.stop()
                self.subscriber_thread.join()
            self.subscriber_thread = None

    def consume(self, res):
        """
        Meant to be reimplemented in child subclass
        This is the main entry point for "consuming" messages from publisher.
        """
        raise NotImplementedError

class ZmqSubscriber(Subscriber):
    """
    Subscriber loaded up with some tools for receiving and deserializing messages
    from a publisher.

    Example:

    ```python
    # example_zmq_subscriber.py

    class MyZmqSubscriber(ZmqSubscriber)
        def consume(self, res):
            print(res)

    uri = "PYRO:MyPublisher@localhost:9093"
    sub = MyZmqSubscriber(uri)
    sub.start_subscribing()
    ```

    Attributes:
        proxy (proxy like object): Some Proxy like object, namely something
            like Pyro4.Proxy.
        context (zmq.Context.instance): zmq context
        serializer_name (str): Name of serializer
        serializer (serializer like object): Some object with `loads` method
    """
    def __init__(self, uri_or_proxy, logger=None, proxy_class=AsyncProxy):
        """
        Args:
            uri_or_proxy (str/URI/proxy like object): Either a URI or a proxy-like
                object. If we pass a uri, then we automatically create a proxy
                using the proxy_class keyword argument
        Keyword Args:
            logger (logging.getLogger): logging instance (None)
            proxy_class (type): Class for creating proxy-like object from URI. (AsyncProxy)
        """
        super(ZmqSubscriber, self).__init__(logger=logger)
        if isinstance(uri_or_proxy, Pyro4.core.URI):
            self.proxy = proxy_class(uri_or_proxy)
        else:
            self.proxy = uri_or_proxy
        self.context = zmq.Context.instance()
        self.serializer_name = self.proxy.serializer_name
        self.serializer = self.proxy.serializer

    def __getattr__(self, attr):
        return getattr(self.proxy, attr)

    def start_subscribing(self, *args,**kwargs):
        super(ZmqSubscriber, self).start_subscribing()

        def subscriber_thread_factory(address, serializer):
            self.logger.debug("start_subscribing.subscriber_thread_factory: address {}".format(address))
            host, port = address.split(":")
            if host == "*":
                host = "localhost"
            subscriber_thread = SubscriberThread(
                self.context, serializer,
                target=self._consume_msg,host=host, port=port
            )
            self.subscribing_started = True
            subscriber_thread.start()
            return subscriber_thread

        if self.subscribing_started:
            return
        elif self.subscribing_paused:
            self.unpause_subscribing()

        if self.subscribing_stopped:
            if self.subscriber_thread is None: self.subscriber_thread = {}
            res = self.proxy.start_publishing(*args,**kwargs)
            self.logger.debug("start_subscribing: res: {}".format(res))
            for name in res:
                publisher_info = res[name]
                serializer = self.serializer[name]
                self.subscriber_thread[name] = subscriber_thread_factory(publisher_info["address"], serializer)

    def _consume_msg(self, msg):
        """Deserialize the message from server and ship off to self.consume"""
        self.emit("consume", msg)
        self.consume(msg)
        return msg

    def consume(self, res):
        """Meant to be reimplemented in child subclass"""
        return res
