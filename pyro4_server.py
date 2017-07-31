# pyro4_server.py
import logging
import os
import signal
import threading
import time
import datetime

import Pyro4

from support.tunneling import Tunnel, TunnelingException
from pyro3_util import full_name
from pyro4_util import arbitrary_tunnel, check_connection

__all__ = ["Pyro4Server"]
__version__ = "0.1.0"
module_logger = logging.getLogger(__name__)

def blocking(fn):
    """
    This decorator will make it such that the server can do
    nothing else while fn is being called.
    """

    def wrapper(*args, **kwargs):
        lock = args[0].lock
        with lock:
            res = fn(*args, **kwargs)
        return res

    return wrapper


def non_blocking(fn):
    """
    Proceed as normal unless a functuon with the blocking
    decorator has already been called
    """

    def wrapper(*args, **kwargs):
        lock = args[0].lock
        while lock.locked():
            time.sleep(0.01)
        time.sleep(0.01)
        res = fn(*args, **kwargs)
        return res

    return wrapper

class Pyro4ServerError(Pyro4.errors.CommunicationError):
    pass

class Pyro4Server(object):
    """
    A super class for Pyro4 servers.
    """
    def __init__(self, name, simulated=False, local=False, logfile=None):
        """
        Setup logging for the server, in addition to creating a
        lock. Subclasses of this class can interact directly with the lock,
        or through the blocking and non-blocking decorators.
        Args:
            name (str): The name of the Pyro server.
            simulated (bool): Simulation mode bool
            local (bool): Local run bool
        """
        self._logfile = kwargs.get("logfile", "")
        self.logger = logging.getLogger(module_logger.name+"."+name)
        self.lock = threading.Lock()
        self._simulated = simulated
        if self._simulated:
            self.logger.name = self.logger.name + ".simulator"
            self.logger.info("Running in simulation mode")
        self._local = local
        self._name = name
        self._running = False
        self._tunnel = None
        self._remote_ip = None
        self._remote_port = None
        self._proc = []
        self.server_uri = None
        self.daemon_thread = None
        self.daemon = None

    @property
    def logfile(self):
        return self._logfile

    #@Pyro4.expose
    def running(self):
        with self.lock:
            return self._running

    #@Pyro4.expose
    @property
    def name(self):
        return self._name

    #@Pyro4.expose
    @property
    def locked(self):
        return self.lock.locked()

    #@Pyro4.expose
    @property
    def simulated(self):
        """
        Is the server returning simulated (fake) data?
        """
        return self._simulated

    #@Pyro4.expose
    @property
    def local(self):
        return self._local

    #@Pyro4.expose
    def ping(self):
        return True

    def handler(self, signum, frame):
        """
        Define actions that should occur before the server
        is shut down.
        """
        try:
            self.logger.info("Closing down server.")
            self.close()
        except Exception as e:
            self.logger.error("Error shutting down daemon: {}".format(e), exc_info=True)
        finally:
            os.kill(os.getpid(), signal.SIGKILL)

    def launch_server(self, remote_server_name='localhost',
                            remote_port=22,
                            ns_host='localhost',
                            ns_port=9090,
                            local_forwarding_port=None,
                            remote_username=None,
                            tunnel_username=None,
                            threaded=False):
        """
        Launch server, remotely or locally. Assumes there is a nameserver registered on
        ns_host/ns_port.

        Args:
            remote_server_name (str): The name of the remote server.
                If we supply the name of a JPL domain, then uses support.tunneling.Tunnel
                to create a tunnel to the desired location
        Keyword Args:
            remote_port (int):
            ns_host:
            ns_port:
            threaded:

        Returns:

        """
        if remote_server_name == 'localhost':
            self._remote_ip = "localhost"
            return self._launch_server_local(ns_host, ns_port, threaded=threaded)
        elif remote_server_name in full_name:
            self._tunnel = Tunnel(remote_server_name, username=tunnel_username)
            self._remote_ip = "localhost"
            self._remote_port = self._tunnel.port
        else:
            self._remote_ip = remote_server_name # means we supplied an actual ip address.
            self._remote_port = remote_port

        # now with tunnel in place (or not depending on condition), we can create
        # further ssh tunnels to allow us to register object.
        # First establish what port to use for local forwarding
        if not local_forwarding_port:
            local_forwarding_port = ns_port

        # Create tunnel to nameserver
        proc_ns = arbitrary_tunnel(self._remote_ip, 'localhost', local_forwarding_port, ns_port,
                                port=self._remote_port, username=remote_username)

        self.logger.debug("")
        self._proc.append(proc_ns)
        # now check the tunnel
        success = check_connection(Pyro4.locateNS, timeout=2, args=('localhost', local_forwarding_port))
        self.logger.debug("Lauching server.")
        if success:
            self._launch_server_local('localhost', ns_port,
                                      create_tunnel=True,
                                      threaded=threaded,
                                      username=remote_username,
                                      port=self._remote_port,
                                      reverse=True)
        else:
            raise TunnelingException("Couldn't create tunnel to remote nameserver")

    def _launch_server_local(self, ns_host, ns_port, create_tunnel=False, threaded=False, **kwargs):
        """
        Connect to a Pyro name server. This also sets up the program such that
        a kill command (ctrl+c) will attempt to call close on the server before exiting.
        This is useful in the case of an APC server, as it is necessary to issue
        the close command before exiting a program with a socket connection to the APC.
        Args:
            ns_host (str): The name server host.
            ns_port (int): The name server port.
            kwargs: For arbitrary_tunnel
        kwargs:
            - create_tunnel (bool): Whether or not to create a tunnel to the remote object.
            - threaded (bool): If we're running this on a thread, then we can't use signaling.
        """
        self.logger.info("Connecting to the Pyro nameserver.")

        self.daemon = Pyro4.Daemon()
        self.server_uri = self.daemon.register(self)
        if create_tunnel:
            obj_host, obj_port = self.server_uri.location.split(":")
            arbitrary_tunnel(self._remote_ip, 'localhost', obj_port, obj_port, **kwargs)

        self.logger.debug("Server uri is {}".format(self.server_uri))
        self.ns = Pyro4.locateNS(port=ns_port, host=ns_host)
        self.ns.register(self._name, self.server_uri)
        self.logger.info("{} available".format(self._name))

        if not threaded:
            signal.signal(signal.SIGINT, self.handler)
        else:
            pass
        with self.lock:
            self._running = True
        self.logger.debug("Starting request loop")
        self.daemon.requestLoop(self.running)

    def close(self):
        """
        Close down the server.
        If we're running this by itself, this gets called by the signal handler.

        If we're running the server's daemon's requestLoop in a thread, then we
        might proceed as follows:

        ```
        s = PyroServer("CoolPyroServer")
        # The true argument is necessary so we don't attempt to call signal handler
        t = threading.Thread(target=s.connect, args=('localhost', 9090, True))
        t.start()
        # Do some other fresh stuff.
        s.close()
        t.join()
        ```
        """
        with self.lock:
            self._running = False
            self.daemon.unregister(self)
            # if we use daemon.close, this will hang forever in a thread.
            # This might appear to hang.

            self.daemon.shutdown()
            # remove the name/uri from the nameserver so we can't try to access
            # it later when there is no daemon running.
            try:
                self.ns.remove(self._name)
            except Pyro4.errors.ConnectionClosedError as err:
                self.logger.debug("Connection to object already shutdown: {}".format(err))

            for proc in self._proc:
                proc.kill()


class Pyro4PublisherServer(Pyro4Server):

    def __init__(self, name, publisher_thread_class,
                            publisher_thread_kwargs={},
                            bus=None,
                            obj=None, **kwargs):

        Pyro4Server.__init__(self, name, obj=obj, **kwargs)
        self.bus = bus
        self.publisher_thread_class = publisher_thread_class
        self.publisher_thread_kwargs = publisher_thread_kwargs
        self.publisher = self.publisher_thread_class(self, bus=self.bus, **self.publisher_thread_kwargs)
        self._publishing_started = False

    #@Pyro4.expose
    @property
    def publishing_started(self):
        return self._publishing_started

    #@Pyro4.expose
    def start_publishing(self):
        """
        Start publishing power meter readings
        Returns:
            None
        """
        if self._publishing_started:
            return
        self._publishing_started = True
        self.logger.info("Starting to publish power meter readings")

        if self.publisher.stopped():
            self.publisher = self.publisher_thread_class(self, bus=self.bus, **self.publisher_thread_kwargs)
            self.publisher.daemon = True

        self.publisher.start()

    #@Pyro4.expose
    def stop_publishing(self):
        """
        Stop the publisher.
        Returns:
            None
        """
        self.publisher.stop()
        self.publisher.join()
        self._publishing_started = False

    #@Pyro4.expose
    def pause_publshing(self):
        """
        Pause the publisher
        Returns:
            None
        """
        self.publisher.pause()

    #@Pyro4.expose
    def unpause_publishing(self):
        """
        Unpause the publisher
        Returns:
            None
        """
        self.publisher.unpause()

if __name__ == '__main__':

    # msg = Pyro4Message(1, False, {'el': 0.0})
    # from TAMS_BackEnd.examples.basic_pyro4_server import BasicServer

    server = Pyro4Server("TestServer", simulated=True)

    # print(msg['timestamp'])
    # @Pyro4.expose
    # class BasicServer(object):
    #
    #     def __init__(self):
    #         pass
    #
    #     def square(self, x):
    #
    #         return x**2
    #
    # server = Pyro4Server("BasicServer", obj=BasicServer(),loglevel=logging.DEBUG)
    # server.launch_server('192.168.0.143', remote_port=2222, remote_username='dean', ns_host='localhost', ns_port=2224)
