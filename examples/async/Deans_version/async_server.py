"""
An async_method decorator causes results or messages to be sent to the async
client's callback handler. See 'async_client.py'.  Note that the callback may
be used multiple times, assuming that the client continues to listen.

The return value is None unless the server is instantiated by the process using
its methods, rather than invoking them via a proxy.
"""
#import logging
#import os
#import sys


from support.pyro import async as pyro_async
from support.pyro import config, Pyro4Server


class BasicServer(Pyro4Server):

    def __init__(self):
        super(BasicServer, self).__init__(obj=self)

    @pyro_async.async_method
    def square(self, x):
        print("BasicServer.square: x={}".format(x))
        res = x**2
        #self.square.cb_info["cb_handler"].square_handler(res)
        self.square.cb(res)
        #self.square.cb_info["cb_handler"].square_handler(("again:", res))
        self.square.cb(("again:", res))

    @pyro_async.async_method
    def repeat(self, word, times, delimiter=", "):
        print("BasicServer.repeat: word={}, times={}".format(word, times))
        res = delimiter.join([word for i in range(times)])
        #self.repeat.cb_info["cb_handler"].repeat_handler(res)
        self.repeat.cb(res)

    @config.expose
    def simple(self, value):
        return value


if __name__ == "__main__":
    #logging.basicConfig(level=logging.ERROR)
    server = BasicServer()
    server.launch_server(
        ns=False,
        objectId="BasicServer",
        objectPort=9091)
