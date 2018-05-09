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
from ..util import PausableThread, iterative_run
from ..async import async_method, EventEmitter

__all__ = [
    "ZmqPublisher",
    "SingleSocketPublisherManager",
    "MultiSocketPublisherManager"
]

module_logger = logging.getLogger(__name__)

class PublisherThread(PausableThread):
    """
    A thread whose 'target' gets called repeatedly until told to pause or stop.

    Attributes:
        event_emitter (EventEmitter): Whenever the threads private threading.Events
            are `set` or `clear`ed, the emitter indicates as such.
        callback (callable): The thread's target
        callback_args (list/tuple): arguments to the thread's target
        callback_kwargs (dict): keyword arguments to the thread's target
    """
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
    """
    A publisher thread with a zmq.Context instance and a serializer.
    I'm careful to abide by thread safety rules, and I thought that creating
    zmq "socket" connections inside threads would be smarter than creating
    those connections outside the thread and passing them to the thread instance.
    Example:

    .. code-block:: python

        # contextualized_publisher_thread_example.py
        import time
        import json

        import zmq

        def publish():
            time.sleep(1.0) # publish every second
            return "hello"

        context = zmq.Context.instance()
        serializer = json
        contextualized_publisher_thread = ContextualizedPublisherThread(context, serializer, target=publish)
        contextualized_publisher_thread.start()

    Attributes:
        context (zmq.Context.instance): zmq context
        serializer (object): some object with a "dumps" method
        host (str): host for zmq socket
        port (int): port for zmq socket
        address (str): zmq socket addresss
        socket (zmq.Socket): zmq socket instance
    """
    def __init__(self, context, serializer, host="localhost", port=0, **kwargs):
        """
        Args:
            context (zmq.Context.instance): zmq context
            serializer (object): some object with a "dumps" method
            host (str, optional): publisher host. Defaults to "localhost"
            port (int, optional): publisher port. Defaults to 0 (random).
            **kwargs: passed to super class
        """
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
    """
    Push the results of the publishing function to a queue.

    Attributes:
        queue (Queue.Queue): A FIFO thread-safe queue.
    """
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

    Attributes:
        lock (threading.Lock): lock for thread safety
        publisher_thread (thread-like object): a thread-like object where the
            Publisher's publish method is called repeatedly, in general.
        _publishing_started (bool): boolean indicating whether publisher has started
        _publishing_stopped (bool): boolean indicating whether publisher is stopped
        _publishing_paused (bool): boolean indicating whether publisher is paused
        _name (str): name of Publisher
        emitter (EventEmitter): EventEmitter object.
    """
    def __init__(self, name=None):
        """
        Keyword Args:
            name (str): Publisher name
        """
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

    @name.setter
    def name(self, new_name):
        self._name = new_name

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
        """
        Reimplement this in a child class.
        Use this method to start publishing.
        """
        raise NotImplementedError

    def pause_publishing(self, *args, **kwargs):
        """
        Reimplement this in a child class.
        Use this method to pause publishing.
        """
        raise NotImplementedError

    def unpause_publishing(self, *args, **kwargs):
        """
        Reimplement this in a child class.
        Use this method to unpause an alreay paused publisher.
        """
        raise NotImplementedError

    def stop_publishing(self, *args, **kwargs):
        """
        Reimplement this in a child class.
        Use this method to stop a publisher that is running.
        """
        raise NotImplementedError

    def publish(self):
        """
        Reimplement this in a child class.
        This method defines the publishing action. This method
        gets called repeatedly in the context of publishing threads.
        """
        raise NotImplementedError

@config.expose
class ZmqPublisher(Publisher):
    """
    ZMQ Publisher base class. This is a publisher that is specifically
    meant to send information over zmq sockets. This is meant to be subclassed,
    and the ``publish`` method reimplemented.

    Examples:

    .. code-block:: python

        # basic_zmq_pub_sub.py

        from support.pyro import zmq

        class BasicZMQPublisher(zmq.ZmqPublisher):
            def publish(self):
                res = {"data":[random.random() for i in range(10)],
                        "timestamp":datetime.datetime.utcnow()}
                time.sleep(1.0)
                print("publishing res: {}".format(res))
                return res

    Attributes:
        context (zmq.Context.instance): zmq context
        _serializer_name (str): name of serializer
        _serializer (serializer like object): Some object with `dumps` method
        _publishing_address (str): the publisher's socket address
    """
    def __init__(self,name=None, serializer=Pyro4.config.SERIALIZER):
        """
        Args:
            name (str, optional): passed to super class (None)
            serialize (serializer like object, optional): Some object with `dumps` method (Pyro4.config.SERIALIZER)
        """
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

        Examples:

        Server side:

        .. code-block:: python

            >>> publisher = SomeSubClassOfZmqPublisher()
            >>> publisher.start_publishing()
            >>> publisher.start_publishing(port=50001)

        Client side:

        Say we've got a server running that controls our publisher.
        That server has some ``uri``.

        .. code-block:: python

            >>> proxy = Pyro4.Proxy(uri)
            >>> sub = SomeSubClassOfZmqSubscriber(proxy)
            >>> sub.start_publishing()

        The above example will only start publishing -- it won't start
        subscribing client side.

        Args:
            host (str, optional): publishing host
            port (int, optional): publishing port
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
    When we create a child class, we populate the publishers attribute with
    individual Publisher objects.

    Example:

    .. code-block:: python

        # example_single_socket_publisher_manager

        from support.pyro import zmq

        class MyPublisher(zmq.Publisher):
            def __init__(self,n,*args, **kwargs):
                super(MyPublisher, self).__init__(*args, **kwargs)
                self.n = n

            def publish(self):
                return "hello from {}".format(n)

        class MySingleSocketPublisher(SingleSocketPublisherManager):
            def __init__(self,**kwargs):
                super(MySingleSocketPublisher).__init__(**kwargs)
                self.publishers = [
                    MyPublisher(i) for i in xrange(10)
                ]

        pub = MySingleSocketPublisher()
        pub.start_publishing()
        # OR:
        pub = SingleSocketPublisherManager()
        pub.publishers = [
            MyPublisher(i) for i in xrange(10)
        ]
        pub.start_publishing()

    In the above example, note that each publisher is a subclass of ``Publisher``,
    not ``ZmqPublisher``. This is because we don't need the machinery to start, pause,
    unpause, and stop publishers within each of the individual publishers -- the
    SingleSocketPublisherManager subclass takes care of all that.

    Attributes:
        publishers (list): list of publisher objects
        queue (Queue.Queue): FIFO thread safe queue.
        context (zmq.Context.instance): zmq context
        _publishing_address (str): zmq socket publisher address
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

        Args:
            host (str, optional): publishing host
            port (int, optional): publishing port
        Returns:
            dict: message with publishing status and publishing address.
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
    own socket connection. Usage is similar to SingleSocketPublisherManager.

    Examples:

    .. code-block:: python

        class MyPublisher(zmq.ZmqPublisher):
            def __init__(self,n,*args, **kwargs):
                super(MyPublisher, self).__init__(*args, **kwargs)
                self.n = n

            def publish(self):
                return "hello from {}".format(n)

        class MyMultiSocketPublisher(MultiSocketPublisherManager):
            def __init__(self,**kwargs):
                super(MyMultiSocketPublisher).__init__(**kwargs)
                self.publishers = [
                    MyPublisher(i) for i in xrange(10)
                ]

        pub = MySingleSocketPublisher()
        pub.start_publishing()
        # OR:
        pub = SingleSocketPublisherManager()
        pub.publishers = [
            MyPublisher(i) for i in xrange(10)
        ]
        pub.start_publishing()

    Attributes:
        publishers (list): List of publishers.
        _publishing_addresses (dict): dictionary of individual publisher addresses.
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

        Examples:

        .. code-block:: python

            >>> publisher = MyMultiSocketPublisher()
            >>> publisher._publisher_action("start_publishing")

        The above is the same as the following:

        .. code-block:: python

            >>> publisher = MyMultiSocketPublisher()
            >>> publisher.start_publishing()

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
