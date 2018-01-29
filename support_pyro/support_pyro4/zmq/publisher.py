import threading
import sys
import time

import Pyro4
import zmq

from ..pyro4_server import Pyro4Server, config
from ..util import PausableThread, EventEmitter, iterative_run
from ..async import async_method
from .util import SocketSafetyWrapper

__all__ = ["PublisherThread", "Publisher"]

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
class Publisher(Pyro4Server):
    """
    Publisher base class. The publish method is meant to be
    reimplemented in child classes.
    """
    def __init__(self, *args, **kwargs):
        self._context = zmq.Context.instance()
        self._lock = threading.Lock()
        self._publisher_thread = None
        self._serializer_name = kwargs.pop("serializer", Pyro4.config.SERIALIZER)
        self._serializer = Pyro4.util.get_serializer(self._serializer_name)
        super(Publisher, self).__init__(*args,**kwargs)

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
        self._publisher_thread = ContextualizedPublisherThread(
                self._context, self._serializer, target=self.publish
        )
        self._publisher_thread.start()
        msg = "publishing started"
        self.start_publishing.cb(msg)

    @async_method
    def pause_publishing(self):
        if self._publisher_thread is not None:
            with self._lock:
                self._publisher_thread.pause()
        msg = "publishing paused"
        self.start_publishing.cb(msg)

    @async_method
    def unpause_publishing(self):
        if self._publisher_thread is not None:
            with self._lock:
                self._publisher_thread.unpause()
        msg = "publishing unpaused"
        self.start_publishing.cb(msg)

    @async_method
    def stop_publishing(self):
        if self._publisher_thread is not None:
            with self._lock:
                self._publisher_thread.stop()
            self._publisher_thread.join()
            self._publisher_thread = None
        msg = "publishing stopped"
        self.stop_publishing.cb(msg)

    def publish(self):
        """
        Reimplement this in order to call a method
        """
        raise NotImplementedError
