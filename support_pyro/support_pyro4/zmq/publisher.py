import threading
import sys
import time

import Pyro4
import zmq

from ..pyro4_server import Pyro4Server
from ..util import PausableThread, EventEmitter
from ..async import async_method

__all__ = ["PublisherThread", "Publisher"]

class PublisherThread(PausableThread):

    def __init__(self, *args, **kwargs):
        super(PublisherThread, self).__init__(*args, **kwargs)
        self.event_emitter = EventEmitter()

    def run(self):
        while True:
            if self.stopped():
                break
            if self.paused():
                time.sleep(0.001)
                continue
            else:
                self._running_event.set()
                if sys.version_info[0] == 2:
                    self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
                else:
                    self._target(*self._args, **self._kwargs)
                self._running_event.clear()

    def stop_thread(self):
        self.event_emitter.emit("stop")
        return super(PublisherThread, self).stop_thread()

    def pause_thread(self):
        self.event_emitter.emit("pause")
        return super(PublisherThread, self).pause_thread()

    def unpause_thread(self):
        self.event_emitter.emit("unpause")
        return super(PublisherThread, self).unpause_thread()

class Publisher(Pyro4Server):
    """
    Publisher base class. The publish method is meant to be
    reimplemented in child classes.
    """
    def __init__(self, *args, **kwargs):
        self._context = zmq.Context.instance()
        self._socket = None
        self._lock = threading.Lock()
        self._publisher_thread = None
        self._serializer_name = kwargs.pop("serializer", Pyro4.config.SERIALIZER)
        self._serializer = Pyro4.util.get_serializer(self._serializer_name)
        super(Publisher, self).__init__(*args,**kwargs)

    def publish(self):
        """
        Reimplement this in order to call a method
        """
        raise NotImplementedError

    @async_method
    def start_publishing(self, host="localhost", port=9091, threaded=True):
        """
        Start publishing. This can either be called server side or client side.
        Keyword Args:

        """
        socket = self._context.socket(zmq.PUB)

        def publisher():
            results = self.publish()
            socket.send(self._serializer.dumps(results))

        if host == "localhost":
            host = "*"
        socket.bind("tcp://{}:{}".format(host, port))
        self._socket = socket

        if threaded:
            self._publisher_thread = PublisherThread(target=publisher)
            self._publisher_thread.daemon = True
            self._publisher_thread.start()
        else:
            while True:
                publisher()
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
        if self._socket is not None:
            self._socket.close()
            self._socket = None

        msg = "publishing stopped"
        self.start_publishing.cb(msg)
