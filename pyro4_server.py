# pyro4_server.py
import logging
import os
import signal
import threading
import time
import datetime

import Pyro4
from pyro4tunneling import Pyro4Tunnel, TunnelError
# from pyro4tunneling.util import check_connection, arbitrary_tunnel

__all__ = ["Pyro4Server","Pyro4ServerError"]
__version__ = "0.1.0"

module_logger = logging.getLogger(__name__)

def blocking(func):
    """
    This decorator will make it such that the server can do
    nothing else while func is being called.
    """
    def wrapper(self, *args, **kwargs):
        lock = self.lock
        with lock:
            res = func(self, *args, **kwargs)
        return res
    return wrapper


def non_blocking(func):
    """
    Proceed as normal unless a functuon with the blocking
    decorator has already been called
    """

    def wrapper(self, *args, **kwargs):
        lock = self.lock
        while lock.locked():
            time.sleep(0.01)
        time.sleep(0.01)
        res = func(self, *args, **kwargs)
        return res

    return wrapper

class Pyro4ServerError(Pyro4.errors.CommunicationError):
    pass

class Pyro4Server(object):
    """
    A super class for Pyro4 servers.
    """
    def __init__(self, name, simulated=False, logfile=None):
        """
        Setup logging for the server, in addition to creating a
        lock. Subclasses of this class can interact directly with the lock,
        or through the blocking and non-blocking decorators.
        Args:
            name (str): The name of the Pyro server.
            simulated (bool): Simulation mode bool
            local (bool): Local run bool
        """
        self._name = name
        self._simulated = simulated
        self._logfile = logfile
        self.logger = logging.getLogger(module_logger.name+"."+name)
        self._local = None
        self._running = False

        self.tunnel = None
        self.remote_ip = None
        self.remote_port = None
        self.proc = []
        self.server_uri = None
        self.daemon_thread = None
        self.daemon = None
        self.lock = threading.Lock()

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
        """
        Method to call if one wants to test connection to server.
        If created a Pyro4.Proxy object using this server, one can also
        use the following snippet:

        ```python
        ns = Pyro4.locateNS()
        uri = ns.locate("<object_name>")
        p = Pyro4.Proxy(uri)
        p._pyroBind()
        ```

        Or use `p.ping()`, which will internally call `p._pyroBind` anyways.
        """
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
                            remote_username=None,
                            ns_host='localhost',
                            ns_port=9090,
                            obj_port=0,
                            obj_id=None,
                            local=True,
                            local_forwarding_port=None,
                            threaded=False,
                            reverse=False):
        """
        Launch server, remotely or locally. Assumes there is a nameserver registered on
        ns_host/ns_port.
        Keyword Args:
            remote_server_name (str): The host of remote server ("localhost")
                Note that even if this is "localhost" this does not mean
                that we're registering object on the local server.
                There could be a tunnel in place that uses "localhost".
            remote_port (int): The port by which to access remote server (22)
            remote_username (str): The username on the server on which we want to register object.
            ns_host (str): The namserver host on the remote server ("localhost")
            ns_port (int): The nameserver port on the remote server (9090)
            obj_port (int): The port on which to register object on remote nameserver (0)
            local (bool): Whether or not we're registering this object on a local name server.
                If this is true, then we act as if we're registering an object in the normal
                Pyro4 manner. (True)
            local_forwarding_port (int): The local forwarding port to use, if not the same as
                the one generated by Pyro4. (None)
            threaded (bool): Whether or not to run this independently or inside another program. (False)
            reverse (bool): Whether or not to create reverse tunnel, so we can access remotely registered
                object locally.
        """
        self.tunnel = Pyro4Tunnel(remote_server_name=remote_server_name,
                                    remote_username=remote_username,
                                    ns_host=ns_host,
                                    ns_port=ns_port,
                                    local=local,
                                    local_forwarding_port=local_forwarding_port)

        self.daemon = Pyro4.Daemon(port=obj_port)
        self.tunnel.register_remote_daemon(self.daemon, reverse=reverse) # this sets up the tunnel
        self.server_uri = self.daemon.register(self,objectId=obj_id)
        self.logger.debug("Server uri is {}".format(self.server_uri))
        self.tunnel.ns.register(self._name, self.server_uri)
        self.logger.info("{} available".format(self._name))
        if not threaded:
            signal.signal(signal.SIGINT, self.handler)
        else:
            pass
        with self.lock:
            self._running = True
        self.logger.debug("Starting request loop")
        self.daemon.requestLoop(self.running)
    #     # if remote_server_name == 'localhost':
    #     #     self._remote_ip = "localhost"
    #     #     return self._launch_server_local(ns_host, ns_port, threaded=threaded)
    #     # elif remote_server_name in full_name:
    #     #     self._tunnel = Tunnel(remote_server_name, username=tunnel_username)
    #     #     self._remote_ip = "localhost"
    #     #     self._remote_port = self._tunnel.port
    #     # else:
    #     #     self._remote_ip = remote_server_name # means we supplied an actual ip address.
    #     #     self._remote_port = remote_port
    #
    #     # now with tunnel in place (or not depending on condition), we can create
    #     # further ssh tunnels to allow us to register object.
    #     # First establish what port to use for local forwarding
    #     if not local_forwarding_port:
    #         local_forwarding_port = ns_port
    #
    #     # Create tunnel to nameserver
    #     proc_ns = arbitrary_tunnel(self._remote_ip, 'localhost', local_forwarding_port, ns_port,
    #                             port=self._remote_port, username=remote_username)
    #
    #     self.logger.debug("")
    #     self._proc.append(proc_ns)
    #     # now check the tunnel
    #     success = check_connection(Pyro4.locateNS, timeout=2, args=('localhost', local_forwarding_port))
    #     self.logger.debug("Lauching server.")
    #     if success:
    #         self._launch_server_local('localhost', ns_port,
    #                                   create_tunnel=True,
    #                                   threaded=threaded,
    #                                   username=remote_username,
    #                                   port=self._remote_port,
    #                                   reverse=True)
    #     else:
    #         raise TunnelingException("Couldn't create tunnel to remote nameserver")
    #
    # def _launch_server_local(self, ns_host, ns_port, create_tunnel=False, threaded=False, **kwargs):
    #     """
    #     Connect to a Pyro name server. This also sets up the program such that
    #     a kill command (ctrl+c) will attempt to call close on the server before exiting.
    #     This is useful in the case of an APC server, as it is necessary to issue
    #     the close command before exiting a program with a socket connection to the APC.
    #     Args:
    #         ns_host (str): The name server host.
    #         ns_port (int): The name server port.
    #         kwargs: For arbitrary_tunnel
    #     kwargs:
    #         - create_tunnel (bool): Whether or not to create a tunnel to the remote object.
    #         - threaded (bool): If we're running this on a thread, then we can't use signaling.
    #     """
    #     self.logger.info("Connecting to the Pyro nameserver.")
    #
    #     self.daemon = Pyro4.Daemon()
    #     self.server_uri = self.daemon.register(self)
    #     if create_tunnel:
    #         obj_host, obj_port = self.server_uri.location.split(":")
    #         arbitrary_tunnel(self._remote_ip, 'localhost', obj_port, obj_port, **kwargs)
    #
    #     self.logger.debug("Server uri is {}".format(self.server_uri))
    #     self.ns = Pyro4.locateNS(port=ns_port, host=ns_host)
    #     self.ns.register(self._name, self.server_uri)
    #     self.logger.info("{} available".format(self._name))
    #
    #     if not threaded:
    #         signal.signal(signal.SIGINT, self.handler)
    #     else:
    #         pass
    #     with self.lock:
    #         self._running = True
    #     self.logger.debug("Starting request loop")
    #     self.daemon.requestLoop(self.running)

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
                self.tunnel.ns.remove(self._name)
            except Pyro4.errors.ConnectionClosedError as err:
                self.logger.debug("Connection to object already shutdown: {}".format(err))
            for proc in self.proc:
                proc.kill()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = Pyro4Server("TestServer", simulated=True)
    server.launch_server(local=True, ns_port=9090, obj_port=9091,obj_id="Pyro4Server.TestServer")
