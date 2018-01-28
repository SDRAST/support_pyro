from __future__ import print_function
import time
import json

import zmq
import serpent
import Pyro4

from .configuration import config
from .pyro4_server import Pyro4Server, Pyro4ServerError
from .util import PausableThread, iterative_run
from .async import CallbackProxy

__all__ = ["ZmqPublisherThread","Pyro4PublisherThread", "Pyro4PublisherServer"]

class ZmqPublisherThread(PausableThread):

    def __init__(self, update_rate, data_cb,context,address,
                        topic="",
                        data_cb_args=None,
                        data_cb_kwargs=None,
                        serializer="serpent",
                        **kwargs):

        PausableThread.__init__(self, **kwargs)
        self.update_rate = update_rate
        self.data_cb = data_cb
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(address)
        self.topic = topic
        if not data_cb_args: data_cb_args = ()
        if not data_cb_kwargs: data_cb_kwargs = {}
        self.data_cb_args = data_cb_args
        self.data_cb_kwargs = data_cb_kwargs

        if serializer == "serpent":
            self.serializer = serpent
        elif serializer == "json":
            self.serializer = json
        else:
            raise Pyro4ServerError("Don't recognize serializer {}".format(serializer))

    @iterative_run
    def run(self):
        data = self.data_cb(*self.data_cb_args, **self.data_cb_kwargs)
        # self.logger.debug("Sending {} on socket".format(self.serializer.dumps(data)))
        self.socket.send(self.topic+self.serializer.dumps(data))
        time.sleep(self.update_rate)

    def stop_thread(self):
        super(ZmqPublisherThread, self).stop_thread()
        self.socket.close()

class Pyro4PublisherThread(PausableThread):
    """
    A Pausable Thread that will publish data to any registered callbacks,
    given some data_cb callback function.
    The run function calls the data_cb function, and then calls all registered callbacks.
    """
    def __init__(self,
                update_rate,
                data_cb,
                data_cb_args=None,
                data_cb_kwargs=None,
                cb_info=None,
                socket_info=None,
                **kwargs):

        PausableThread.__init__(self, **kwargs)
        self.update_rate = update_rate
        self.data_cb = data_cb

        if not data_cb_args: data_cb_args = ()
        if not data_cb_kwargs: data_cb_kwargs = {}
        self.data_cb_args = data_cb_args
        self.data_cb_kwargs = data_cb_kwargs

        if cb_info:
            if not isinstance(cb_info, list):
                self.cb_info = [cb_info]
            else:
                self.cb_info = cb_info
            for i, info in enumerate(self.cb_info):
                if isinstance(info, AsyncCallback):
                    self.cb_info[i] = info
                elif isinstance(info, dict):
                    self.cb_info[i] = AsyncCallback(cb_info=info, socket_info=socket_info)
        else:
            self.cb_info = []

    @iterative_run
    def run(self):
        data = self.data_cb(*self.data_cb_args,**self.data_cb_kwargs)
        for cb in self.cb_info:
            cb.cb(data)
        time.sleep(self.update_rate)

    def register_callback(self, cb_info, socket_info=None):
        """
        Register some callback with the Publisher.
        args:
            cb_info (dict):
        """
        with self._lock:
            if isinstance(cb_info, AsyncCallback):
                self.cb_info.append(cb_info)
            elif isinstance(cb_info, dict):
                self.cb_info.append(AsyncCallback(cb_info=cb_info, socket_info=socket_info))

    def change_rate(self, new_rate):
        """
        Change the rate at which the publisher updates.
        Args:
            new_rate (float): Time in seconds to wait before calling self.data_cb
        """
        with self._lock:
            self.update_rate = new_rate


class Pyro4PublisherServer(Pyro4Server):
    """
    """
    backend = "zmq"
    def __init__(self, **kwargs):
        """
        """
        Pyro4Server.__init__(self, **kwargs)
        self.publisher_thread = None
        self.publisher_context = None
        self._publisher_address = None

    def create_zmq_context(self,host=None, port=None):
        """
        Create a zmq socket of the publisher type.
        This method sets the publisher_address and publisher_socket
        attributes
        Keyword Arguments:
            host (str):
            port (str):
        """
        if host is None: host = "*"
        if port is None: port = Pyro4.socketutil.findProbablyUnusedPort()
        context = zmq.Context.instance()
        address = "tcp://{}:{}".format(host, port)

        self._publisher_address = address
        self.publisher_context = context

        return context, address

    @config.expose
    @property
    def publisher_address(self):
        return self._publisher_address

    def get_publisher_data(self):
        raise NotImplementedError("Subclass needs to implement this method")

    @config.expose
    def start_publishing(self,update_rate,
                        create_zmq_context_kwargs=None,
                        pyro4_publisher_thread_kwargs=None,
                        zmq_publisher_thread_kwargs=None):

        if create_zmq_context_kwargs is None: create_zmq_context_kwargs = {}
        if pyro4_publisher_thread_kwargs is None: pyro4_publisher_thread_kwargs = {}
        if zmq_publisher_thread_kwargs is None: zmq_publisher_thread_kwargs = {}
        self.logger.debug("Starting Publishing")
        if self.publisher_thread is not None:
            self.logger.info(("Cannot start publishing: Publishing already started. "
                              "If you're attempting to restart publishing, then first "
                              "call `stop_publishing` method, and then `start_publishing`"))
            return

        if self.backend == "pyro4":

            self.publisher_thread = Pyro4PublisherThread(update_rate, self.get_publisher_data,
                                                    **pyro4_publisher_thread_kwargs)


        elif self.backend == "zmq":
            try:
                if self.publisher_context is None and self._publisher_address is None:
                    self.create_zmq_context(**create_zmq_context_kwargs)

                self.publisher_thread = ZmqPublisherThread(update_rate,
                                                            self.get_publisher_data,
                                                            self.publisher_context,
                                                            self._publisher_address,
                                                            **zmq_publisher_thread_kwargs)
            except Exception as err:
                self.logger.error(err, exc_info=True)

        try:
            self.publisher_thread.start()
        except Exception as err:
            self.logger.error(err, exc_info=True)

    @config.expose
    def unpause_publishing(self):
        """
        Unpause publishing thread
        """
        self.logger.debug("Unpausing publishing")
        if self.publisher_thread is None:
            self.logger.debug("No publisher thread to unpause")
        else:
            self.publisher_thread.unpause_thread()

    @config.expose
    def pause_publishing(self):
        """
        Pause publishing thread
        """
        self.logger.debug("Pausing publishing")
        if self.publisher_thread is None:
            self.logger.debug("No publisher thread to pause")
        else:
            self.publisher_thread.pause_thread()

    @config.expose
    def stop_publishing(self):
        """
        Stop publishing thread
        """
        self.logger.debug("Stopping publishing")
        if self.publisher_thread is None:
            self.logger.debug("No publisher thread to pause")
        else:
            self.publisher_thread.pause_thread()
            self.publisher_thread.stop_thread()
            self.publisher_thread = None

    @config.expose
    def register_callback(self, cb_info, socket_info=None):
        """
        Register some callback with the publisher thread, if using the Pyro4
        publishing backend.
        Args:
            cb_info (dict): Callback info dictionary.
        Keyword Args:
            socket_info (dict): Optional socket info argument.
        """
        if self.backend == "pyro4":
            if self.publisher_thread is not None:
                self.publisher_thread.register_callback(cb_info, socket_info=socket_info)

        elif self.backend == "zmq":
            self.logger.debug(("register_callback not implemented for zmq backend "
                                "as it is unaware of client side callbacks."))
