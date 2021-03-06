from __future__ import print_function
import time
import logging

from Pyro5.compatibility import Pyro4

__all__ = ['AutoReconnectingProxy', 'Pyro4Client']

module_logger = logging.getLogger(__name__)

class AutoReconnectingProxy(Pyro4.Proxy):
    """
    A Pyro proxy that automatically recovers from a server disconnect.
    It does this by intercepting every method call and then it first 'pings'
    the server to see if it still has a working connection. If not, it
    reconnects the proxy and retries the method call.
    Drawback is that every method call now uses two remote messages (a ping,
    and the actual method call).

    TAKEN FROM PYRO4 DISCONNECT EXAMPLE

    """
    def _pyroInvoke(self, *args, **kwargs):
        # We override the method that does the actual remote calls: _pyroInvoke.
        # If there's still a connection, try a ping to see if it is still alive.
        # If it isn't alive, reconnect it. If there's no connection, simply call
        # the original method (it will reconnect automatically).
        if self._pyroConnection:
            try:
                Pyro4.message.Message.ping(self._pyroConnection, hmac_key=None)    # utility method on the Message class
            except (Pyro4.errors.ConnectionClosedError, Pyro4.errors.CommunicationError):
                self._pyroReconnect()
        return super(AutoReconnectingProxy, self)._pyroInvoke(*args, **kwargs)

class Pyro4Client(object):
    """
    21-03-2018: Untested.
    A simple wrapper around Pyro4.Proxy.
    This is meant to be subclassed. Client side methods are meant to be put here.
    """
    def __init__(self, tunnel, proxy_name, use_autoconnect=False, logger=None):
        """
        Intialize a connection the Pyro server.
        Args:
            tunnel ()

        """
        if logger is None:
            self.logger = logging.getLogger(module_logger.name + "." + proxy_name)
        else:
            self.logger = logger
        self.proxy_name = proxy_name
        self.tunnel = tunnel
        self.server = self.tunnel.get_remote_object(self.proxy_name, auto=use_autoconnect)
        self.connected = True

    def __getattr__(self, attr):
        """
        This allows us to interact with the server as if it were a normal
        Python object.
        args:
            - attr (str): The attribute we're trying to access
        """
        return getattr(self.server, attr)

    def check_connection(self):
        """
        Check to make sure server is still active. If not, attempt to reestablish
        connection.
        """
        t0 = time.time()
        try:
            pinged = self.server.ping()
        except (Pyro4.errors.DaemonError, AttributeError, Pyro4.errors.CommunicationError):
            self.connected = False
            self.logger.info("Trying to reconnect...")
            self.server = self.tunnel.get_pyro_object(self.proxy_name)
            self.logger.info("New server: {}".format(self.server))
        self.logger.debug("Took {:.2f} seconds to check connection.".format(time.time() - t0))
