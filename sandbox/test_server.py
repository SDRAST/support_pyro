from __future__ import print_function
import sys
import logging
import datetime
import argparse

import Pyro4

def setup_logging():

    timestamp = datetime.datetime.utcnow().strftime("%j-%Hh%Mm")
    logfile='example_{}.log'.format(timestamp)
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    fh = logging.FileHandler(logfile)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logging.getLogger('').addHandler(fh)

def simple_parse_args():

    parser = argparse.ArgumentParser(description="Start TestServer")
    parser.add_argument("--ns_host", "-nsn", dest='ns_host', action='store', default='localhost',
                        help="Specify a host name for the Pyro name server. Default is localhost")

    parser.add_argument("--ns_port", "-nsp", dest='ns_port', action='store',default=50000,type=int,
                        help="Specify a port number for the Pyro name server. Default is 50000.")

    return parser

def main():
    setup_logging()
    from pyro_support.pyro4_server import Pyro4Server
    parsed = simple_parse_args().parse_args()
    server = Pyro4Server("TestServer", simulated=True)
    server.launch_server(local=True, ns_port=parsed.ns_port,ns_host=parsed.ns_host,
                        obj_port=0, obj_id="Pyro4Server.TestServer")

if __name__ == '__main__':
    main()
