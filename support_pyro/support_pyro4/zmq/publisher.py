import logging
import threading
import uuid
try:
    import queue
except ImportError:
    import Queue as queue
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

module_logger = logging.getLogger(__name__)

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

@config.expose
class Publisher(object):
    """
    Publisher base class. The start_publishing, pause_publishing,
    unpause_publishing, stop_publishing and publish methods are meant to be
    reimplemented in child classes.
    """
    def __init__(self, name=None):
        self.lock = threading.Lock()
        self.publisher_thread = None
        self._publishing_started = False
        self._publishing_stopped = True
        self._publishing_paused = False
        if name is None: name = uuid.uuid4().hex
        self._name = name
        self.emitter = EventEmitter()

    @property
    def name(self):
        return self._name

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
    def __init__(self,name=None, serializer=Pyro4.config.SERIALIZER):
        super(ZmqPublisher, self).__init__(name=name)
        self.context = zmq.Context.instance()
        self._serializer_name = serializer
        self._serializer = Pyro4.util.get_serializer(self._serializer_name)
        self._publishing_address = None

    @property
    def publishing_address(self):
        return self._publishing_address

    @property
    def serializer_name(self):
        return {self._name:self._serializer_name}

    @property
    def serializer(self):
        return {self._name:self._serializer}

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
            self._publishing_address = {self._name:"{}:{}".format(host,port)}
            self._publishing_started = True
            publisher_thread.start()
            return publisher_thread

        msg = {self._name:{
                "status":"publishing started",
                "address":None
        }}

        if self.publisher_thread is None:
            self.publisher_thread = publisher_thread_factory(host, port)
            msg[self._name]["address"] = self._publishing_address[self._name]
            return msg
        else:
            stopped = self.publisher_thread.stopped()
            if stopped:
                self.publisher_thread.join()
                self.publisher_thread = publisher_thread_factory(host, port)
                msg[self._name]["address"] = self._publishing_address[self._name]
                return msg
            paused = self.publisher_thread.paused()
            if paused:
                return self.unpause_publishing()
            running = self.publisher_thread.running()
            if running:
                msg[self._name]["address"] = self._publishing_address[self._name]
                return msg

    def pause_publishing(self):
        msg = {self.name:{
            "status": "publishing paused",
            "address": self._publishing_address
        }}
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.pause()
        self._publishing_paused = True
        return msg

    def unpause_publishing(self):
        msg = {self.name:{
            "status": "publishing paused",
            "address": self._publishing_address
        }}
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.unpause()
        self._publishing_paused = False
        return msg

    def stop_publishing(self):
        msg = {self.name:{
            "status": "publishing paused",
            "address": self._publishing_address
        }}
        if self.publisher_thread is not None:
            with self.lock:
                self.publisher_thread.stop()
            self.publisher_thread.join()
            self.publisher_thread = None
            self._publishing_stopped = True
            return msg
        else:
            msg[self._name]["status"] = "no publishing to stop"
            msg[self._name]["address"] = None
            return msg

    def publish(self):
        """
        Reimplement this in order to call a method
        """
        raise NotImplementedError

@config.expose
class SingleSocketPublisherManager(Publisher):
    """
    Manage several publishers on a single socket.
    """
    def __init__(self,name=None):
        super(SingleSocketPublisherManager, self).__init__(name=name)
        self.publishers = []
        self.queue = queue.Queue()
        self.context = zmq.Context.instance()
        self._publishing_address = None

    @property
    def publishing_address(self):
        return self._publishing_address

    @property
    def serializer(self):
        return {self._name: self.publishers[0]._serializer}

    @property
    def serializer_name(self):
        return {self._name:self.publishers[0]._serializer_name}

    def start_publishing(self, host="localhost", port=0):
        """
        Instead of simply calling each Publisher's start_publishing method,
        we actually grab each one's publish method and stuff it in a
        SingleSocketPublisherThread instance.

        The result of each Publisher's publish method will get "put" in a Queue
        via an instance of a Single SingleSocketPublisherThread.

        A master thread, an instance of a ContextualizedPublisherThread, will then
        "get" the queue (remove the last element from the queue), and publish
        that to the socket.
        """
        serializers = [pub._serializer for pub in self.publishers]
        assert all([s == serializers[0] for s in serializers[1:]]), "Serializers must be the same for all publishers"

        for publisher in self.publishers:
            name = publisher.name
            single_socket_publisher_thread = SingleSocketPublisherThread(self.queue, target=publisher.publish)
            single_socket_publisher_thread.start()
            publisher.publisher_thread = single_socket_publisher_thread

        self.publisher_thread = ContextualizedPublisherThread(self.context, self.serializer[self._name],
                                        host=host, port=port, target=self.publish)
        host = self.publisher_thread.host
        port = self.publisher_thread.port
        self._publishing_address = {self._name:"{}:{}".format(host,port)}
        self.publisher_thread.start()

        msg = {
            self._name:{
                "address":self._publishing_address[self._name],
                "status":"publishing started"
            }
        }

        return msg

    def pause_publishing(self):
        msg = {
            self._name:{
                "address":self._publishing_address[self._name],
                "status":"publishing paused"
            }
        }
        if self.publisher_thread is not None:
            self.publisher_thread.pause()
        for publisher in self.publishers:
            msg = publisher.pause_publishing()
        return msg

    def unpause_publishing(self):
        msg = {
            self._name:{
                "address":self._publishing_address[self._name],
                "status":"publishing unpaused"
            }
        }
        if self.publisher_thread is not None:
            ret_msg = self.publisher_thread.unpause()
        for publisher in self.publishers:
            msg = publisher.unpause_publishing()
        return msg

    def stop_publishing(self):
        msg = {
            self._name:{
                "address":self._publishing_address[self._name],
                "status":"publishing stopped"
            }
        }
        if self.publisher_thread is not None:
            ret_msg = self.publisher_thread.stop()
        for publisher in self.publishers:
            msg = publisher.stop_publishing()
        return msg

    def publish(self):
        res = self.queue.get()
        self.queue.task_done() # not sure if this is necessary, I read about it in Python docs.
        return res

@config.expose
class MultiSocketPublisherManager(Publisher):
    """
    Manage many independent socket connections -- each publisher gets its
    own socket connection
    """
    def __init__(self,name=None):
        """
        This should be reimplemented in a child class.
        """
        super(MultiSocketPublisherManager, self).__init__(name=name)
        self.publishers = []
        self._publishing_addresses = {}

    def _publisher_action(self, method_name):
        """
        Pausing, stopping, starting and unpausing publisher looks pretty
        much the same, except that the method has a different name.

        Calling self._publisher_action("pause_publishing") is the same as
        iterating through each publisher and calling its respective
        "pause_publishing" method.
        """
        res = {}
        for publisher in self.publishers:
            name = publisher.name
            msg = getattr(publisher, method_name)()
            self._publishing_addresses[name] = msg[name]["address"]
            res.update(msg)
        return res

    @property
    def serializer_name(self):
        return {p._name:p._serializer_name for p in self.publishers}

    @property
    def serializer(self):
        res = {}
        return {p._name:p._serializer for p in self.publishers}

    @property
    def publishing_started(self):
        return self._publisher_action("publishing_started")

    @property
    def publishing_paused(self):
        return self._publisher_action("publishing_paused")

    @property
    def publishing_stopped(self):
        return self._publisher_action("publishing_stopped")

    @property
    def publishing_addresses(self):
        return self._publishing_addresses

    def start_publishing(self):
        return self._publisher_action("start_publishing")

    def pause_publishing(self):
        return self._publisher_action("pause_publishing")

    def unpause_publishing(self):
        return self._publisher_action("unpause_publishing")

    def stop_publishing(self):
        return self._publisher_action("stop_publishing")

    def publish(self):
        pass
