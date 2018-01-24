## Proposed Syntax

I want a Pyro4 server (read: Daemon) and client (read: Proxy) that are
asynchronous out of the box. You simply pass a callback to the server method,
and the server calls the callback when the result of the server method is
done.

```python
# example_server.py

from Pyro4Async import async

class SimpleAsyncServer(object):

    @async
    def method1(self, x):
        self.method1.callback(x**2)

with Daemon({"host":"localhost", "port":9090}) as daemon:
    simple_async_server = SimpleAsyncServer()
    uri = daemon.register(simple_async_server, {"objectId":"SimpleAsyncServer"})
    daemon.requestLoop()
```

```python
# example_client.py
from Pyro4Async import AsyncProxy

def method1_callback(res):
    print(res)

AsyncProxy.register(method1_callback)
proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:9090")
proxy.method1(2,callback=method1_callback)
```

```python
# example_client1.py
import Pyro4

from Pyro4Async import AsyncProxy

class SimpleClient(object):

    @Pyro4.expose
    def method1_callback(self,res):
        print(res)

client = SimpleClient()
proxy = AsyncProxy("PYRO:SimpleAsyncServer@localhost:9090")
proxy.register(client)
proxy.method1(2,callback="method1_callback")
```
