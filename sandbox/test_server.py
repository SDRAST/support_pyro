import logging

import Pyro4

Pyro4.config.REQUIRE_EXPOSE=True
logging.basicConfig(level=logging.DEBUG)

from pyro_support.pyro4_server import Pyro4Server

def main():
    server = Pyro4Server("TestServer", simulated=True)
    server.launch_server(local=True, ns_port=9090, obj_port=9091, obj_id="Pyro4Server.TestServer")

if __name__ == '__main__':
    main()
