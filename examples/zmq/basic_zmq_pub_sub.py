import datetime
import random
import time

import Pyro4

from support.pyro import zmq, Pyro4Server

class BasicZMQPublisher(zmq.ZmqPublisher):
    def publish(self):
        res = {"data":[random.random() for i in range(10)],
                "timestamp":datetime.datetime.utcnow()}
        time.sleep(1.0)
        print("publishing res: {}".format(res))
        return res

class BasicZMQSubscriber(zmq.ZmqSubscriber):

    def consume(self, res):
        print("receiving res: {}".format(res))
        return res

def run_pub():
    pub = BasicZMQPublisher()
    server = Pyro4Server(obj=pub)
    info = server.launch_server(ns=False,
                      objectId=pub.__class__.__name__,
                      objectPort=50002,
                      threaded=True,
                      tunnel_kwargs={
                        "local":True
                      }
    )
    return info["uri"]

def run_sub(uri):
    sub_proxy = Pyro4.Proxy(uri)
    sub = BasicZMQSubscriber(sub_proxy)
    sub.start_subscribing()
    while True:
        pass

if __name__ == '__main__':
    uri = run_pub()
    run_sub(uri)
