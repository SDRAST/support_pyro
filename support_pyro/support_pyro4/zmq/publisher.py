import threading
import sys
import time

import Pyro4
import zmq

from ..pyro4_server import Pyro4Server, config
from ..util import PausableThread, EventEmitter, iterative_run
from ..async import async_method

__all__ = ["Publisher"]

class PublisherThread(PausableThread):

    def __init__(self, *args, **kwargs):
        super(PublisherThread, self).__init__(*args, **kwargs)
        self.event_emitter = EventEmitter()
        self.logger.debug("__init__: current thread: {}".format(threading.current_thread()))

    @iterative_run
    def run(self):
        if sys.version_info[0] == 2:
            self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
        else:
            self._target(*self._args, **self._kwargs)

    def stop_thread(self):
        self.event_emitter.emit("stop")
        return super(PublisherThread, self).stop_thread()

    def pause_thread(self):
        self.event_emitter.emit("pause")
        return super(PublisherThread, self).pause_thread()

    def unpause_thread(self):
        self.event_emitter.emit("unpause")
        return super(PublisherThread, self).unpause_thread()

class ContextualizedPublisherThread(PublisherThread):

    def __init__(self, context, serializer, host="localhost", port=0, **kwargs):
        super(ContextualizedPublisherThread, self).__init__(**kwargs)
        self.context = context
        if sys.version_info[0] == 2:
            callback = self._Thread__target
        else:
            callback = self._target
        self.callback = callback
        self.serializer = serializer
        if host == "localhost":
            host = "*"
        self.host = host
        if port == 0:
            port = Pyro4.socketutil.findProbablyUnusedPort()
        self.port = port
        self.address = "tcp://{}:{}".format(self.host, self.port)
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(self.address)

    @iterative_run
    def run(self):
        res = self.callback()
        if not self.socket.closed:
            self.socket.send(self.serializer.dumps(res))

    def stop_thread(self):
        res = super(ContextualizedPublisherThread, self).stop_thread()
        if self.socket is not None:
            self.socket.close()
        return res

@config.expose
class Publisher(object):
    """
    Publisher base class. The publish method is meant to be
    reimplemented in child classes.
    """
    def __init__(self, *args, **kwargs):
        self.context = zmq.Context.instance()
        self.lock = threading.Lock()
        self.publisher_thread = None
        self.emitter = EventEmitter()
        self._serializer_name = kwargs.pop("serializer", Pyro4.config.SERIALIZER)
        self._serializer = Pyro4.util.get_serializer(self._serializer_name)
        self._publishing_started = False
        self._publishing_stopped = True
        self._publishing_paused = False
        self._publishing_address = None
        self.emitter = EventEmitter()
        super(Publisher, self).__init__(*args,**kwargs)

    @property
    def publishing_started(self):
        return self._publishing_started

    @property
    def publishing_stopped(self):
        return self._publishing_stopped

    @property
    def publishing_paused(self):
        return self._publishing_paused

    @property
    def publishing_address(self):
        return

    @property
    def serializer_name(self):
        return self._serializer_name

    @property
    def serializer(self):
        return self._serializer

    @async_method
    def start_publishing(self, host="localhost", port=0):
        """
        Start publishing. This can either be called server side or client side.
        Keyword Args:
        """
        def publisher_thread_factory(host, port):
            publisher_thread = ContextualizedPublisherThread(
                    self.context, self._serializer, target=self.publish,
                    host=host, port=port
            )
            host = publisher_thread.host
            port = publisher_thread.port
            self._publishing_address = "{}:{}".format(host,port)
            self._publishing_started = True
            publisher_thread.start()
            return publisher_thread

        msg = {
            "status":"publishing started",
            "address":None
        }

        if self.publisher_thread is None:
            self.publisher_thread = publisher_thread_factory(host, port)
            msg["address"] = self._publishing_address
            self.start_publishing.cb(msg)
            return
        else:
            stopped = self.publisher_thread.stopped()
            if stopped:
                self.publisher_thread.join()
                self.publisher_thread = publisher_thread_factory(host, port)
                msg["address"] = self._publishing_address
                self.start_publishing.cb(msg)
                return
            paused = self.publisher_thread.paused()
            if paused:
                return self.unpause_publishing(cb_info=self.start_publishing.cb_info)

    @async_method
    def pause_publishing(self):
        msg = {
            "status": "publishing paused",
            "address": self._publishing_address
        }
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.pause()
        self._publishing_paused = True
        self.pause_publishing.cb(msg)

    @async_method
    def unpause_publishing(self):
        msg = {
            "status": "publishing unpaused",
            "address": self._publishing_address
        }
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.unpause()
        self._publishing_paused = False
        self.unpause_publishing.cb(msg)

    @async_method
    def stop_publishing(self):
        msg = {
            "status": "publishing stopped",
            "address": self._publishing_address
        }
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.stop()
            self.publisher_thread.join()
            self.publisher_thread = None
            self._publishing_stopped = True
            self.stop_publishing.cb(msg)
        else:
            msg["status"] = "no publishing to stop"
            msg["address"] = None
            self.stop_publishing.cb(msg)

    def publish(self):
        """
        Reimplement this in order to call a method
        """
        raise NotImplementedError
