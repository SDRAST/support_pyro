import sys

from random import randint
from support.pyro import async, config, Pyro4Server
from time import sleep

class ServerClient(Pyro4Server):

    def __init__(self):
        super(ServerClient, self).__init__(obj=self)
        self.proxy = async.AsyncProxy("PYRO:BasicServer@localhost:9091")

    @async.async_method
    def delayed_repeat(self, word, number):
        wait = randint(0,5)
        self.delayed_repeat.cb("[calling remote method 'repeat' in %d s]" % wait)
        sleep(wait)
        res=self.proxy.repeat(word, number, callback=self.repeat_callback)
        self.delayed_repeat.cb("[remote method 'repeat' returned %s]" % res)
        return res

    @async.async_method
    def delayed_square(self, value):
        wait = randint(0,5)
        self.delayed_square.cb("[calling remote method 'repeat' in %d s]" % wait)
        sleep(wait)
        res=self.proxy.square(2, callback=self.square_callback)
        self.delayed_square.cb("[remote method 'square' returned %s]" % res)
        return res
    
    @config.expose
    def simple(self, value):
        wait = randint(0,5)
        sleep(wait)
        value=self.proxy.simple(3.1415926)
        return value
    
    @async.async_callback
    def square_callback(self, res):
        print "square handler got:", res
        self.delayed_square.cb(res)
        # return res

    @async.async_callback
    def repeat_callback(self, res):
        print "repeat handler got:", res
        self.delayed_repeat.cb(res)
        

if __name__ == "__main__":
    server = ServerClient()
    server.launch_server(ns=False,objectId="BasicServer",objectPort=9092)

#####################

srvrcli = ServerClient()

while True:
  try:
    pass
  except KeyboardInterrupt:
    sys.exit()
