"""
Pyro4 compatibility layer for RA's support module.
"""

import logging
import time
import os
import signal
import re

import Pyro4

from support.tunneling import Tunnel
from support.process import invoke, search_response, BasicProcess
from support.logs import logging_config
from pyro3_util import full_name
from pyro4_client import AutoReconnectingProxy
full_name = full_name.copy()
try:
    full_name.pop('localhost')
except KeyError:
    pass
module_logger = logging.getLogger(__name__)
logging_config(logger=module_logger, loglevel=logging.DEBUG)

class Pyro4ObjectDiscoverer(object):
    """
    An class used to represent a set of ssh tunnels to a Pyro4 object located remotely.
    This is meant to be a replacement for Tom's support.pyro.get_device_server function.
    This does not just work for JPL tunnels, however. We can tunnel to arbitrary IP addresses
    and gain access to Pyro objects as well.

    Example Usage:
    If we want to get the URI of the APC Pyro object on crux, we would do the following:

    ```
    crux_tunnel = Pyro4ObjectDiscoverer("crux", remote_ns_host='localhost', remote_ns_port=50000,
                                        tunnel_username='ops', username='ops')
    apc = crux_tunnel.get_pyro_object('APC')
    ```

    To create the APC client, we would have to send the URI to TAMS_BackEnd.clients.APCClient:

    ```
    apc_client = TAMS_BackEnd.clients.APCClient(proxy=apc)
    # now we can call APC methods.
    apc_client.get_azel()
    ```

    Let's say I wanted to find an object on a remote server, but that remote server wasn't on
    the JPL network. I might do the following:

    ```
    remote_discoverer = Pyro4ObjectDiscoverer('192.168.0.2', remote_ns_host='localhost', remote_ns_port=2224,
                                                username='user', port=2222)
    basic_server = remote_discoverer.get_pyro_object('BasicServer')
    print(basic_server.name)
    >> u'BasicServer'
    ```


    Public Attributes:
        remote_server_name (str): The name or ip address of the remote server
        remote_port (int): The remote port to be used for tunneling.
            This should be a listening port on the remote server.
        remote_ns_port (int): The remote nameserver port
        remote_ns_host (str): The remote nameserver host name
        local_forwarding_port (int): The local port on which to listen;
            the local port we used for port forwarding
        tunnel_username (str): The username for the creation of a support.tunneling.Tunnel.
            This could be, for example, a login to the JPL ops gateway.
        username (str): The username to use for port forwarding. On crux, this would be 'ops'
        logger (logging.getLogger): Return value of logging_util.logging_config
        processes (list): A list of the running processes. These processes might be
            subprocess.Popen instances, or BasicProcess instances.
        uris (dict): A dictionary of Pyro4 URI objects. The keys are the server names
            on the remote nameserver.
    Public Methods:
        get_pyro_object_uri: Creates a tunnel to the remote server (if not in place already)
            and then creates tunnels to the nameserver and the requested object.
        cleanup: Kill the processes that are associated with the nameserver and the requested
            object(s).

    Private Attributes:
        _local (bool): Is this a local connection (ie, on this same computer)?
    """

    def __init__(self,
                 remote_server_name='localhost',
                 remote_port=None,
                 remote_ns_port=50000,
                 remote_ns_host='localhost',
                 local_forwarding_port=None,
                 tunnel_username=None,
                 remote_username=None,
                 loglevel=logging.INFO,
                 **kwargs):
        """
        Create a Pyro4ObjectDiscoverer object.
        Args:
            remote_server_name (str): Name or ip of remote server.
        Keyword Args:
            remote_port (int): The remote listening port.
            remote_ns_port (int): The remote nameserver port
            remote_ns_host (str): The remote nameserver host name
            local_forwarding_port (int): The local port on which to listen;
                the local port we used for port forwarding
            tunnel_username (str): The username for the creation of a support.tunneling.Tunnel.
                This could be, for example, a login to the JPL ops gateway.
            username (str): The username to use for port forwarding. On crux, this would be 'ops'
            **kwargs: For logging_util.logging_config
        """
        self.remote_server_name = remote_server_name
        self.remote_ns_host = remote_ns_host
        self.remote_ns_port = remote_ns_port
        if not local_forwarding_port: local_forwarding_port = remote_ns_port
        self.local_forwarding_port = local_forwarding_port
        self.tunnel_username = tunnel_username
        self.remote_username = remote_username
        logger = logging.getLogger(module_logger.name + ".Pyro4Tunnel")
        self.logger = logging_config(logger=logger, loglevel=loglevel, **kwargs)
        self.processes = []

        if remote_server_name in full_name.keys():
            self.local = False
            self.logger.debug("Checking for existing Tunnel.")
            self.tunnel = Tunnel(remote_server_name, username=tunnel_username)
            self.remote_port = self.tunnel.port
            self.remote_server_ip = 'localhost'
        elif remote_server_name == 'localhost':
            self.remote_server_ip = 'localhost'
            if remote_port:
                self.local = False
                self.remote_port = remote_port
            else:
                self.local = True
        else:
            self.local = False
            self.logger.debug("Provided server name not on JPL network.")
            self.tunnel = None
            self.remote_server_ip = remote_server_name
            self.remote_port = remote_port


        if self.local:
            self.logger.debug("Local nameserver host:port: {}:{}".format(self.remote_ns_host, self.remote_ns_port))
            self.ns = Pyro4.locateNS(host=self.remote_ns_host, port=self.remote_ns_port)
        else:
            self.ns = self.find_nameserver(self.remote_server_ip,
                                           self.remote_ns_host,
                                           self.remote_ns_port,
                                           self.local_forwarding_port,
                                           self.remote_port,
                                           self.remote_username)


        self.uris = {}
        self.requested_objects = []

    def find_nameserver(self,
                        remote_server_ip,
                        remote_ns_host,
                        remote_ns_port,
                        local_forwarding_port,
                        remote_port,
                        remote_username):
        """
        Get the nameserver sitting on remote_ns_port on the remote server.
        We explicitly pass arguments instead of using attributes so we can
        use this method outside of __init__.
        Args:
            remote_server_ip (str): The IP address of remote server.
            remote_ns_host (str): The hostname of the remote nameserver
                (I don't imagine a situation in which this would change)
            remote_ns_port (int): The port of the remote nameserver
            local_forwarding_port (int): The local port to use for forwarding.
            remote_port (int): A listening port on remote
        Returns:
            Pyro4.naming.NameServer instance or
            None if can't be found.
        """

        self.logger.debug("Remote server IP: {}".format(remote_server_ip))
        proc_ns = arbitrary_tunnel(remote_server_ip, 'localhost', local_forwarding_port,
                                   remote_ns_port, username=remote_username, port=remote_port)

        self.processes.append(proc_ns)
        if check_connection(Pyro4.locateNS, kwargs={'host': remote_ns_host, 'port': local_forwarding_port}):
            ns = Pyro4.locateNS(host=remote_ns_host, port=local_forwarding_port)
            return ns
        else:
            self.logger.error("Couldn't connect to the remote Nameserver", exc_info=True)
            return None

    def register_daemon(self, daemon):
        """
        Args:
            daemon (Pyro4.Daemon):

        Returns:
        """
        if self.local:
            return None
        else:
            daemon_host, daemon_port = daemon.locationStr.split(":")
            proc_daemon = arbitrary_tunnel(self.remote_server_ip, 'localhost', daemon_port,
                                           daemon_port, username=self.remote_username,
                                           port=self.remote_port, reverse=True)
            self.processes.append(proc_daemon)

    def get_pyro_object(self, remote_obj_name, use_autoconnect=False):
        """
        Say we wanted to connect to the APC server on crux, and the APC server
        was sitting on nameserver port 50000 on crux. We could do this as follows:

        Args:
            remote_obj_name (str): The name of the Pyro object.
        Returns:
            Pyro4.URI corresponding to requested pyro object, or
            None if connections wasn't successful.
        """
        try:
            obj_uri = self.ns.lookup(remote_obj_name)
        except AttributeError:
            self.logger.error("Need to call find_nameserver.")
            return None

        self.requested_objects.append(remote_obj_name)
        if use_autoconnect:
            obj_proxy = AutoReconnectingProxy(obj_uri)
        else:
            obj_proxy = Pyro4.Proxy(obj_uri)

        if self.local:
            return obj_proxy
        elif not self.local:
            obj_host, obj_port = obj_uri.location.split(":")
            proc_obj = arbitrary_tunnel(self.remote_server_ip, 'localhost', obj_port,
                                        obj_port, username=self.remote_username, port=self.remote_port)

            self.processes.append(proc_obj)
            # if check_connection(getattr, args=(obj_proxy, 'name')):  # We are trying to get property, hence getattr
            if check_connection(obj_proxy._pyroBind):
                self.uris[remote_obj_name] = obj_uri
                return obj_proxy
            else:
                self.logger.error("Couldn't connect to the object", exc_info=True)
                return None

    def cleanup(self):
        """
        Kill all the existing tunnels that correspond to processes created
        Returns:
            None
        """
        # try:
        #
        #     ns = self.ns
        #     for name in self.requested_objects:
        #         ns.remove(name)
        # except AttributeError as err:
        #     self.logger.error("cleanup: Couldn't remove requested objects from the nameserver: {}".format(err))

        self.logger.debug("Cleaning up ssh connections.")
        for proc in self.processes:
            proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()

def check_connection(callback, timeout=1.0, attempts=10, args=(), kwargs={}):
    """
    Check to see if a connection is viable, by running a callback.
    Args:
        callback: The callback to test the connection
    Keyword Args:
        timeout (float): The amount of time to wait before trying again
        attempts (int): The number of times to try to connect.
        args: To be passed to callback
        kwargs: To be passed to callback

    Returns:
        bool: True if the connection was successful, False if not successful.
    """
    attempt_i = 0
    while attempt_i < attempts:
        try:
            callback(*args, **kwargs)
        except Exception as e:
            module_logger.debug("Connection failed: {}. Timing out".format(e))
            time.sleep(timeout)
            attempt_i += 1
        else:
            module_logger.info("Successfully connected.")
            return True
    module_logger.error("Connection failed completely.")
    return False


def arbitrary_tunnel(remote_ip, relay_ip,
                     local_port, remote_port,
                     port=22, username='', reverse=False):
    """
    Create an arbitrary ssh tunnel, after checking to see if a tunnel already exists.
    This just spawns the process that creates the tunnel, it doesn't check to see if the tunnel
    has successfully connected.

    Executes the following command:
    ```
    ssh  -p {port} -l {username} -L {local_port}:{relay_ip}:{remote_port} {remote_ip}
    ```
    Args:
        remote_ip (str): The remote, or target ip address.
            For local port forwarding this can be localhost
        relay_ip (str): The relay ip address.
        local_port (int): The local port on which we listen
        remote_port (int): The remote port on which we listen
    Keyword Args:
        port (int): The -p argument for ssh
        username (str): The username to use for tunneling
    Returns:
        subprocess.Popen: if there isn't an existing process corresponding to tunnel:
            or else BasicProcess instance, the corresponds to already running tunnel command.

    """
    #-c arcfour -o ServerAliveInterval=60 -o TCPKeepAlive=no
    # First thing is check to see if the remote_ip is ~/.ssh/config
    home_dir = os.path.expanduser("~")
    ssh_config = os.path.join(home_dir, ".ssh/config")
    with open(ssh_config, 'r') as config:
        contents = config.read()

    pattern = "host (.*)\n"
    hosts = [match for match in re.findall(pattern, contents)]

    r_option = "-L"
    if reverse:
        r_option = "-R"

    if remote_ip in hosts:
        command = "ssh -N {0} {1}:{2}:{3} {4}"
        command = command.format(r_option, local_port, relay_ip, remote_port, remote_ip)
    else:
        command = "ssh -N -l {0} -p {1} {2} {3}:{4}:{5} {6}"
        command = command.format(username, port, r_option, local_port, relay_ip, remote_port, remote_ip)

    command_relay = "{0} {1}:{2}:{3} {4}".format(r_option, local_port, relay_ip, remote_port, remote_ip)
    # module_logger.debug(command_relay)
    ssh_proc = search_response(['ps', 'x'], ['grep', 'ssh'])
    # re_pid = re.compile("\d+")
    # re_name = re.compile("ssh.*")
    for proc in ssh_proc:
        if command_relay in proc:
            module_logger.debug("Found matching process: {}".format(proc))
            # proc_id = int(re_pid.findall(proc)[0])
            # proc_name = re_name.findall(proc)[0]
            return BasicProcess(ps_line=proc, command_name='ssh')
            # return BasicProcess(name=proc_name, pid=proc_id)

    module_logger.debug("Invoking command {}".format(command))
    p = invoke(command)
    return p


if __name__ == '__main__':
    proc = arbitrary_tunnel('localhost', 'localhost', 2222, 50000, port=50046, username='ops')