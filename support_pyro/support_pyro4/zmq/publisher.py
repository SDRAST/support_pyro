import logging
import threading
import queue
import sys
import time

import Pyro4
import zmq

from ..pyro4_server import Pyro4Server, config
from ..util import PausableThread, EventEmitter, iterative_run
from ..async import async_method

__all__ = [
    "ZmqPublisher",
    "SingleSocketPublisherManager",
    "MultiSocketPublisherManager"
]

class PublisherThread(PausableThread):

    def __init__(self, *args, **kwargs):
        super(PublisherThread, self).__init__(*args, **kwargs)
        self.event_emitter = EventEmitter()
        self.logger.debug("__init__: current thread: {}".format(threading.current_thread()))

        if sys.version_info[0] == 2:
            self.callback = self._Thread__target
            self.callback_args = self._Thread__args
            self.callback_kwargs = self._Thread__kwargs
        else:
            self.callback = self._target
            self.callback_args = self._args
            self.callback_kwargs = self._kwargs

    @iterative_run
    def run(self):
        self.callback(*self.callback_args, **self.callback_kwargs)

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

class SingleSocketPublisherThread(PublisherThread):
    def __init__(self, queue, *args, **kwargs):
        super(SingleSocketPublisherThread, self).__init__(*args, **kwargs)
        self.queue = queue

    @iterative_run
    def run(self):
        res = self.callback(*self.callback_args, **self.callback_kwargs)
        self.queue.put(res)


class Publisher(object):
    """
    Publisher base class. The start_publishing, pause_publishing,
    unpause_publishing, stop_publishing and publish methods are meant to be
    reimplemented in child classes.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.publisher_thread = None
        self._publishing_started = False
        self._publishing_stopped = True
        self._publishing_paused = False
        self.emitter = EventEmitter()

    @property
    def publishing_started(self):
        return self._publishing_started

    @property
    def publishing_stopped(self):
        return self._publishing_stopped

    @property
    def publishing_paused(self):
        return self._publishing_paused

    def start_publishing(self, *args, **kwargs):
        raise NotImplementedError

    def pause_publishing(self, *args, **kwargs):
        raise NotImplementedError

    def unpause_publishing(self, *args, **kwargs):
        raise NotImplementedError

    def stop_publishing(self, *args, **kwargs):
        raise NotImplementedError

    def publish(self):
        raise NotImplementedError

@config.expose
class ZmqPublisher(Publisher):
    """
    Publisher base class. The publish method is meant to be
    reimplemented in child classes.
    """
    def __init__(self,serializer=Pyro4.config.SERIALIZER):
        super(ZmqPublisher, self).__init__()
        self.context = zmq.Context.instance()
        self._serializer_name = serializer
        self._serializer = Pyro4.util.get_serializer(self._serializer_name)
        self._publishing_address = None
        self.emitter = EventEmitter()

    @property
    def publishing_address(self):
        return self._publishing_address

    @property
    def serializer_name(self):
        return self._serializer_name

    @property
    def serializer(self):
        return self._serializer

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
            # self.start_publishing.cb(msg)
            return msg
        else:
            stopped = self.publisher_thread.stopped()
            if stopped:
                self.publisher_thread.join()
                self.publisher_thread = publisher_thread_factory(host, port)
                msg["address"] = self._publishing_address
                # self.start_publishing.cb(msg)
                return msg
            paused = self.publisher_thread.paused()
            if paused:
                return self.unpause_publishing()
            running = self.publisher_thread.running()
            if running:
                msg["address"] = self._publishing_address
                return msg
                # return self.unpause_publishing(cb_info=self.start_publishing.cb_info)

    def pause_publishing(self):
        msg = {
            "status": "publishing paused",
            "address": self._publishing_address
        }
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.pause()
        self._publishing_paused = True
        # self.pause_publishing.cb(msg)
        return msg

    def unpause_publishing(self):
        msg = {
            "status": "publishing unpaused",
            "address": self._publishing_address
        }
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.unpause()
        self._publishing_paused = False
        # self.unpause_publishing.cb(msg)
        return msg

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
            return msg
            # self.stop_publishing.cb(msg)
        else:
            msg["status"] = "no publishing to stop"
            msg["address"] = None
            return msg
            # self.stop_publishing.cb(msg)

    def publish(self):
        """
        Reimplement this in order to call a method
        """
        raise NotImplementedError

class SingleSocketPublisherManager(Publisher):
    """
    Manage serveral publishers on a single socket.
    """
    def __init__(self):
        super(SingleSocketPublisherManager, self).__init__()
        self.publishers = {"__order__":[]}
        self.queue = queue.Queue()

    def start_publishing(self, host="localhost", port=0):
        """
        Instead of simply calling each Publisher's start_publishing method,
        we actually grab each one's publish method and stuff it in a
        SingleSocketPublisherThread instance.
        """
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            publisher_thread = SingleSocketPublisherThread(target=publisher.publish)
            publisher_thread.start()
            publisher.publisher_thread = publisher_thread

        self.publisher_thread = ContextualizedPublisherThread(self.context, self.serializer,
                                        host=host, port=port, target=self.publish)
        self.publisher_thread.start()

        return self.publisher_addresses

    def pause_publishing(self):
        self.publisher_thread.pause()
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.pause_publishing()
        return self.publisher_address

    def unpause_publishing(self):
        self.publisher_thread.unpause()
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.unpause_publishing()
        return self.publisher_address

    def stop_publishing(self):
        self.publisher_thread.stop()
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.stop_publishing()
        return self.publisher_address

    def publish(self):
        if not self.queue.empty()
            res = self.queue.get()
            return res

class MultiSocketPublisherManager(Publisher):
    """
    Manage many independent socket connections -- each publisher gets its
    own socket connection
    """

    def __init__(self):
        """
        This should be reimplemented in a child class.
        """
        super(MultiSocketPublisherManager, self).__init__()
        self.publisher_addresses = {}

    @property
    def publishing_started(self):
        started = {}
        for name in self.publishers["__order__"]:
            started[name] = self.publishers.publishing_started()
        return started

    @property
    def publishing_paused(self):
        paused = {}
        for name in self.publishers["__order__"]:
            paused[name] = self.publishers.publishing_paused()
        return paused

    @property
    def publishing_stopped(self):
        stopped = {}
        for name in self.publishers["__order__"]:
            stopped[name] = self.publishers.publishing_stopped()
        return stopped

    def start_publishing(self):
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.start_publishing()
            self.publisher_addresses[name] = msg["address"]
        return self.publisher_addresses

    def pause_publishing(self):
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.pause_publishing()
            self.publisher_addresses[name] = msg["address"]
        return self.publisher_addresses

    def unpause_publishing(self):
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.unpause_publishing()
            self.publisher_addresses[name] = msg["address"]
        return self.publisher_addresses

    def stop_publishing(self):
        for name in self.publishers["__order__"]:
            publisher = self.publishers[name]
            msg = publisher.stop_publishing()
            self.publisher_addresses[name] = msg["address"]
        return self.publisher_addresses

    def publish(self):
        pass
