import logging
import time

from support.pyro import async

class Client(async.AsyncClient):

    def __init__(self, uri):
        super(Client, self).__init__()
        self.proxy = async.AsyncProxy(uri)

    @async.async_callback
    def square_handler(self, res):
        print(res)

    def square(self, x):
        self.proxy.square(x, callback=self.square_handler)

uri = "PYRO:BasicServer@localhost:9091"

client = Client(uri)

client.square(2)

client.wait("square_handler")
