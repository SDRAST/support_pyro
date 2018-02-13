import datetime
import time

import Pyro4

from support.pyro import zmq, Pyro4Server, config

class SinglePublisher(zmq.ZmqPublisher):

    def publish(self):
        res = {"timestamp":datetime.datetime.utcnow()}
        time.sleep(2.0)
        print("publish: {}: {}".format(self.name, res))
        return res

@config.expose
class MultiSocketExample(zmq.MultiSocketPublisherManager):
    def __init__(self):
        super(MultiSocketExample, self).__init__()
        self.publishers = [
            SinglePublisher(name="pub1"),
            SinglePublisher(name="pub2"),
            SinglePublisher(name="pub3")
        ]

class BasicZMQSubscriber(zmq.ZmqSubscriber):
    def consume(self, res):
        print("receiving res: {}".format(res))
        return res

def run_pub():
    pub = MultiSocketExample()
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
    # addresses = sub_proxy.start_publishing()
    # print(addresses)
    sub = BasicZMQSubscriber(sub_proxy)
    sub.start_subscribing()
    while True:
        pass


if __name__ == "__main__":
    uri = run_pub()
    run_sub(uri)
