import logging
import sys
from random import randint

# import Pyro4

from support.pyro import async as pyro_async
from support.pyro import config, Pyro4Server
from time import sleep


class ServerClient(Pyro4Server):

    def __init__(self):
        super(ServerClient, self).__init__(obj=self)
        self.proxy = pyro_async.AsyncProxy("PYRO:BasicServer@localhost:9091")

    @pyro_async.async_method
    def delayed_repeat(self, word, number):
        print("ServerClient.delayed_repeat: word={}, number={}".format(
            word, number))
        wait = randint(0, 5)
        self.delayed_repeat.cb(
            "[calling remote method 'repeat' in %d s]" % wait)
        sleep(wait)
        res = self.proxy.repeat(word, number, callback=self.repeat_handler)
        self.delayed_repeat.cb("[remote method 'repeat' returned %s]" % res)
        return res

    @pyro_async.async_method
    def delayed_square(self, value):
        print("ServerClient.delayed_repeat: value={}".format(value))
        wait = randint(0, 5)
        self.delayed_square.cb("[calling remote method 'repeat' in %d s]" % wait)
        sleep(wait)
        res = self.proxy.square(2, callback=self.square_handler)
        self.delayed_square.cb("[remote method 'square' returned %s]" % res)
        return res

    @config.expose
    def simple(self, value):
        print("ServerClient.simple: value={}".format(value))
        wait = randint(0, 5)
        sleep(wait)
        value = self.proxy.simple(3.1415926)
        return value

    @pyro_async.async_callback
    def square_handler(self, res):
        print("ServerClient.square_handler: got: {}".format(res))
        self.delayed_square.cb(res)

    @pyro_async.async_callback
    def repeat_handler(self, res):
        print("ServerClient.repeat_handler: got {}".format(res))
        self.delayed_repeat.cb(res)


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    server = ServerClient()
    server.launch_server(
        ns=False,
        objectId="BasicServer",
        objectPort=9092)

