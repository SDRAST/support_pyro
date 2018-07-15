## support_pyro
### Version 2.0.0

Pyro4 server and client.

### Dependencies

- pyro4tunneling>=1.2.0
- Pyro4

### Usage

#### `Pyro4Server`

The recommended usage is to subclass `pyro_support.Pyro4Server`.

```python
# new_cool_server.py
import Pyro4

from pyro_support import Pyro4Server

class NewCoolServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(obj=self, name="NewCoolServer")

    @Pyro4.expose
    def new_cool_method(self):
        return "Wow, what a cool method!"


if __name__ == '__main__':
    s = NewCoolServer()
    s.launch_server()
```

Now to interface with this subclass, we do the following:

```python
# new_cool_client.py

import pyro4tunnel

t = pyro4tunneling(local=True)
p = t.get_remote_object("NewCoolServer")
print(p.new_cool_method())
```

Now, when I run `new_cool_client.py` I'll get the following output
(assuming that `new_cool_server.py` is running in the background):

```bash
me@local:/path/to/new_cool_client$ python new_cool_client.py
Wow, what a cool method!
me@local:/path/to/new_cool_client$
```

#### async

Coming soon.

#### zmq

Subscribing:

```python
import Pyro4

from support.pyro import zmq

class MySubscriber(zmq.ZmqSubscriber):

    def consume(self, res):
        # do something with res
        print("Got {} from publisher!".format(res))

if __name__ == "__main__":
    uri = "PYRO:APC@localhost:50001"
    sub = MySubscriber(uri, proxy_class=Pyro4.Proxy) # default is support.pyro.async.AsyncProxy
    # `start_subscribing` will call publisher start publishing method
    # if not already called
    sub.start_subscribing()
```

### Installation

This is meant to be a submodule of the RA `support` package. As a result,
installation is a matter of installing required dependencies:

```
pip install -r requirements.txt
```

### Testing

In the top level directory, type the following:

```bash
/path/to/pyro-support$ python -m unittest discover -s test -t .
```
