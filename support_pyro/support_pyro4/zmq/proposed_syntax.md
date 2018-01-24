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

from pyro4_zmq import Publisher

@Pyro4.expose
class ExamplePublisher(Publisher):
    def publish(self):
        data = {"some_key":"some_value"}
        self.emit(data)
        time.sleep(1.0)

    def square(self, x):
        return x**2

if __name__ == "__main__":
    server = ExamplePublisher()
    with Pyro4.Daemon() as daemon:
        uri = daemon.register(server)
        ns = Pyro4.locateNS()
        ns.register("ExamplePublisher", uri)
        daemon.requestLoop()

```


subscriber.py:

```python
# subscriber.py
import threading

import Pyro4

from pyro4_zmq import Subscriber

class ExampleSubscriber(Subscriber):

    def consume(self, data):
        print(data["some_key"])

if __name__ == "__main__":
    ns = Pyro4.locateNS()
    uri = ns.lookup("ExamplePublisher")
    client = Pyro4.Proxy(uri)
    client.start_publishing() # we could do this server side as well
    subscriber = ExampleSubscriber(client)
    t = threading.Thread(target=subscriber.start_subscribing)
    t.daemon = True
    t.start()
    print(subscriber.square(2))
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
