import threading
import sys
import time

import Pyro4
import zmq

from ..util import PausableThread, EventEmitter

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



class Publisher(object):
    """
    Publisher base class. The publish method is meant to be
    reimplemented in child classes.
    """
    def __init__(self, serializer=Pyro4.config.SERIALIZER):

        self._context = zmq.Context.instance()
        self._socket = None
        self._lock = threading.Lock()
        self.publisher_thread = None
        self._serializer_name = serializer
        self._serializer = Pyro4.util.get_serializer(serializer)

    def publish(self):
        """
        """
        raise NotImplementedError

    def start_publishing(self, host="localhost", port=9091, callback=None, threaded=True):
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
            self.publisher_thread = PublisherThread(target=publisher)
            self.publisher_thread.daemon = True
            self.publisher_thread.start()
        else:
            while True:
                publisher()
        if callback is not None:
            callback(self)

    def pause_publishing(self):

        if self.publisher_thread is not None:
            with self._lock:
                self.publisher_thread.pause()

    def unpause_publishing(self):

        if self.publisher_thread is not None:
            with self._lock:
                self.publisher_thread.unpause()

    def stop_publishing(self):

        if self.publisher_thread is not None:
            with self._lock:
                self.publisher_thread.stop()
            self.publisher_thread.join()
            self.publisher_thread = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None
