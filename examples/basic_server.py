"""
basic_server.py

Example that shows how to subclass Pyro4Server and launch on local nameserver.
"""

from pyro_support import Pyro4Server, config

class BasicServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(self, name='BasicServer')

    @config.expose
    def square(self, x):
        return x**2

if __name__ == '__main__':
    s = BasicServer()
    s.launch_server(local=True, ns_port=parsed.ns_port,ns_host=parsed.ns_host,
                    obj_port=0, obj_id="Pyro4Server.BasicServer")
