"""
Example of using a server instance to access server methods

The first example ignores the server's Pyro4Server superclass and creates a
local instance.  The result is returned.

The second example assumes that the server is a normal Pyro4 server.  It will
accept a connection and allow a method to be invoked but no result is
returned.
"""
from async_server import BasicServer

srvr = BasicServer()
print "instance returned:", srvr.square(2)

from Pyro4 import Proxy

uri = "PYRO:BasicServer@localhost:9091"
proxy = Proxy(uri)
print "proxy returned:", proxy.square(2)



