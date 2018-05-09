import logging
import time

from support.pyro import async

class Client(async.AsyncClient):

    @async.async_callback
    def square_handler(self, res):
        print(res)

uri = "PYRO:BasicServer@localhost:9091"

client = Client(uri)

with client.wait("square_handler"):
    client.square(2, callback=client.square_handler)
