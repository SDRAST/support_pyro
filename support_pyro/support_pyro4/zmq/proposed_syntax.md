## Proposed Syntax

Pyro3 had a built in subscriber/publisher. This can be accomplished with Pyro4,
but with some _significant_ overhead and boilerplate. In addition, my experience
with the messagebus has been less than stellar. When the messsagebus server was
running for a long time I would find that it would not deliver messages, or they
wouldn't even be published in the first place. ØMQ has builtin support for a
publisher/subscriber model with very little code overhead. Additionally, ØMQ
doesn't use any middleware for the publisher/subscriber model.

I propose a simple extension to Pyro4 syntax to allow for ØMQ publishing and
subscribing.

publisher.py:

```python
# publisher.py
import time

import Pyro4

from support_pyro.support_pyro4.zmq.publisher import Publisher
from support_pyro.support_pyro4.async import async_method
from support_pyro.support_pyro4 import config

class ExamplePublisher(Publisher):

    def publish(self):
        data = {"some_key":"some_value"}
        self.emit(data)
        time.sleep(1.0)

    @async_method
    def square_async(self, x):
        self.square.cb(x**2)

    @config.expose
    def square(self, x):
        return x**2

if __name__ == "__main__":
    server = ExamplePublisher()
    server.launch_server(local=True, ns_port=9090,threaded=False)
    # OR
    with Pyro4.Daemon() as daemon:
        uri = daemon.register(server)
        with Pyro4.locateNS() as ns:
            ns.register("ExamplePublisher", uri)
            daemon.requestLoop()
```


subscriber.py:

```python
# subscriber.py
import threading

import Pyro4

from support_pyro.support_pyro4.zmq.subscriber import Subscriber

class ExampleSubscriber(Subscriber):

    def consume(self, data):
        print("from consume method: {}".format(data))

def handler(data):
    print("from handler: {}".format(data))

if __name__ == "__main__":
    ns = Pyro4.locateNS()
    uri = ns.lookup("ExamplePublisher")
    sub = ExampleSubscriber(uri)
    sub.on("consume", handler)
    sub.start_subscribing() # this will automatically call start_publishing if not already called.
```

subscriber.js

```javascript
// subscriber.js
const nro = require("nro") // node remote object

var publishHandler = (data)=>{
    console.log(data)
}

var lookupHandler = (proxy)=>{
    proxy.on("publish", publishHandler)
    proxy.remoteCall("start_publishing",()=>console.log("Publishing Started"))
}

nro.locateNS({port:9090,host:"localhost"},(ns)=>{
    ns.lookup("ExamplePublisher", lookupHandler)
})
```
