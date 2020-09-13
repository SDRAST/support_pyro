"""
An async_method decorator causes results or messages to be sent to the async
client's callback handler. See 'async_client.py'.  Note that the callback may
be used multiple times, assuming that the client continues to listen.

The return value is None unless the server is instantiated by the process using
its methods, rather than invoking them via a proxy.
"""
from support.pyro import async, config, Pyro4Server

class BasicServer(Pyro4Server):

    def __init__(self):
        super(BasicServer, self).__init__(obj=self)

    @async.async_method
    def square(self, x):
        print("(server prints square: x: {})".format(x))
        res = x**2
        self.square.cb(res)
        self.square.cb(("again:", res))
        return res

    @async.async_method
    def repeat(self, word, times, delimiter=", "):
        print("repeat: word: {}, times: {}".format(word, times))
        res = delimiter.join([word for i in range(times)])
        self.repeat.cb(res)
        return res
    
    @config.expose
    def simple(self, value):
        return value

if __name__ == "__main__":
    server = BasicServer()
    server.launch_server(ns=False,objectId="BasicServer",objectPort=9091)
