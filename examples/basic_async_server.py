import argparse

import Pyro4

from support_pyro.support_pyro4.async import async_method

class BasicAsyncServer(object):

    @async_method
    def square(self, x):
        print("square called with argument {}".format(x))
        self.square.cb(x**2)

    @async_method
    def repeat(self, chars, times, delimiter=" "):
        print("repeat called with arguments {} {} {}".format(chars, times, delimiter))
        self.repeat.cb(delimiter.join([chars for i in range(times)]))

def create_parser():
    parser = argparse.ArgumentParser(description="Bind server on a given port")
    parser.add_argument("--port","-p",dest="port",action="store",default=55000, type=int)

    return parser

def main():
    parser = create_parser().parse_args()
    with Pyro4.Daemon(port=parser.port) as daemon:
        server = BasicAsyncServer()
        uri = daemon.register(server, objectId=server.__class__.__name__)
        print("Server uri is\n{}".format(uri))
        daemon.requestLoop()

if __name__ == "__main__":
    main()
