## Moving from Pyro3 to Pyro4

Pyro4 and Pyro3 work in very much the same way, but there are some small differences
between the two packages that can make migrating Pyro3 code to Pyro4 a little
baffling, especially when SSH tunnels are needed.

As with Pyro3, Pyro4 uses a nameserver to manage servers on a specific address.
Pyro4 servers are actually just Python objects that are registered to a `Pyro4.Daemon`.
The Pyro4 nameserver is a `Pyro4.Daemon` as well, just with some special functionality.

Before running any servers, make sure that you have a nameserver running in the
background. The Pyro4 command line tool for this is `pyro4-ns`. On crux, I run
the nameserver on port 50000 (there is no specific reason I chose this port number,
I just couldn't use the default port, 9090, because the Pyro3 nameserver was already
using it).

### Requirements

- Pyro4
- pyro4tunneling (I'm in the process of trying to open source this with NYU,
so the code is hosted on a NYUAD Github repo. This is annoying. Ask me for a .zip
file with the code.)

### Extending from pyro_support.Pyro4Server

The most transparent way to set up a Pyro4 Server is to extend from the
`pyro_support.Pyro4Server` base class.

```python
from __future__ import print_function # Python3 compatibility!

from pyro_support import Pyro4Server, config

class BasicServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(name="BasicServer")

    @config.expose
    def square(self, x):
        return x**2

if __name__ == '__main__':
    server = BasicServer()
    server.launch_server(local=True, remote_server_name='localhost',
                        ns_port=50000, ns_host='localhost')

```

The above code launches an instance of `BasicServer` on the local nameserver.
Note that the `local` keyword is necessary if you don't want to create SSH tunnels.
With the `local` keyword in place, the `launch_server` method is just a boiler plate method
that prevents you from having to write code to create a new `Pyro4.Daemon`, register
the object on the daemon, and launch the daemon. With `local` set to False,
`Pyro4Server` assumes you want to create SSH tunnels.

In this vein, say you want to register your instance of `BasicServer` on crux.
In order to keep this code as generic as possible, _it no longer creates the initial
ssh tunnel to JPL computers_. You will have to create the tunnel yourself, hopefully
using Tom's excellent `ssh-tunnel` Linux command. Say you have the tunnel to crux
running, and you have a nameserver running on crux on port 50000. You can register
`BasicServer` in two ways, depending on how you want to interact with the object.
If you want to be able to register the object remotely and access it locally,
then you'll need to set the `reverse` keyword in the `launch_server` method.
See the following code for an example of reverse and forward server registration.
Using the same definiton of `BasicServer` from above:

```python
...

if __name__ == "__main__":
    server = BasicServer()
    # the following registers the server on crux for access on crux
    server.launch_server(remote_server_name="localhost", port=5XXXX, remote_username="ops",
                        ns_port=50000, ns_host="localhost", reverse=False)

    # the following registers the server on crux for access locally.
    server.launch_server(remote_server_name="localhost", port=5XXXX, remote_username="ops",
                        ns_port=50000, ns_host="localhost", reverse=True)
```

### WBDC2hw_server example

Say I want to migrate wbdc2hw_server.WBDC2hw_server to Pyro4.

I would change `__init__ to the following`:

```python
@Pyro4.expose
class WBDC2hw_server(Pyro4Server, WBDC2hwif):
    """
    Server for interfacing with the Wide Band Down Converter2
    """

    def __init__(self, name, **kwargs):
        """
        """
        Pyro4Server.__init__(self, name=name,**kwargs)
        self.logger.debug("Pyro4Server superclass initialized")
        WBDC2hwif.__init__(self, name)
        self.logger.debug("hardware interface  superclass instantiated")
```
And the bottom of the file becomes the following:

```python
if __name__ == '__main__':
    m = WBDC2hw_server("WBDC-2")
    m.launch_server(remote_server_name="crux", ns_port=50000)
```

Of course, this last bit depends on your configuration. If you need to start a tunnel
to access crux, then do so before running this script. If the "crux" name is
not in "~/.ssh/config" then you'll have to configure `pyro4tunneling` accordingly.

At the end of the day, I would ultimately recommend launching the server locally, and
then accessing it from crux using `pyro4tunneling`. In that case, the these last lines
would be the following:

```python
if __name__ == '__main__':
    m = WBDC2hw_server("WBDC-2")
    m.launch_server(local=True, remote_server_name="localhost", ns_port=50000)

```

For this to work, you'd have to have a nameserver running on the local machine (dss43wbdc, I believe).


### Accessing remote objects

Lets say I've registered an object locally on crux. I can use `pyro4tunneling` to
access it on my local machine.

```python
from __future__ import print_function # Python3 compatibility!
from pyro4tunneling import Pyro4Tunnel

t = Pyro4Tunnel(remote_server_name="localhost", port=5XXXX, remote_username='ops',
                ns_port=50000)
# If I have pyro4tunneling configured (see the next section), I can do the following:
t = Pyro4Tunnel(remote_server_name="crux", ns_port=50000)

basic_server_client = t.get_remote_object("BasicServer")
print(basic_server_client.square(2))

```

### Configuring pyro4tunneling

It's annoying to have to have to type in port and username details everytime you
want to register a server remotely. You can configure pyro4tunneling in a few ways.
I'm copying the configuration section of `pyro4tunneling` README.md here.

As `pyro_support` relies on pyro4tunneling, any configuration you load will
automatically be accessible to `pyro_support.Pyro4Server`

#### Configuration

Let's say that you get tired of writing in the ssh details for a remote machine. `pyro4tunneling` has a few ways of
dealing with this. The first is to add the remote server details to your `~/.ssh/config` file.
This requires no further configuration; `pyro4tunneling` automatically looks in this file to extract ssh configuration information.

You can also provide dictionary or JSON file configurations. A dictionary configuration looks like the following:

```python
from pyro4tunneling import config, Pyro4Tunnel

config.ssh_configure({'remote': ["hostname", "myname", 22]})

tunnel = Pyro4Tunnel('remote',ns_port=9090)
proxy = tunnel.get_remote_object("BasicServer")
```

A JSON file configurations looks like the following:

```python
# json_config.py
from pyro4tunneling import config, Pyro4Tunnel

config.ssh_configure("./pyro4tunneling.json")

tunnel = Pyro4Tunnel('remote',ns_port=9090)
proxy = tunnel.get_remote_object("BasicServer")

```

```json
// pyro4tunneling.json. Note that most parsers won't read comments.
{"remote":["hostname", "username", 22]}
```

### Miscellenous Stuff

#### `Pyro4.expose`

Prior to Pyro4 version 4.46, Pyro4 didn't have a `Pyro4.expose` decorator. For this
reason I've created a `config.expose` method that is version independent. If you're running
Pyro4 version > 4.46, throw `config.expose` on the methods/classes you'd like to expose.
If you run that same code with Pyro4 version < 4.46, it will run just fine, except
it will expose everything. See [here](https://pythonhosted.org/Pyro4/servercode.html#creating-a-pyro-class-and-exposing-its-methods-and-properties)
for more information.

#### Server/client design patterns

The combination of `pyro4tunneling` and `pyro_support` allows one to setup
servers and clients in two ways:

1. Register server locally, and access remotely.
2. Register server remotely, and access locally.

In general, I prefer the first option. Client connections to a server are temporary,
as are any sort of ssh connection. Servers should be running all the time, in the background,
waiting for new client connections. To this end, having the life of a server
dependent on that of an SSH connection (however stable) is not the best idea.
Having a server registered on a nameserver that is located on the LAN is fine.

#### `flaskify`

I'm currently working on a mechanism to expose methods of `Pyro4Server`
subclasses to a flask-socketio server. The intended, and current implementation is
as follows:

```python
...

app, socketio, server = BasicServer.flaskify()

@app.route("/")
def home():
    return "Howdy there!"

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)

```

and client-side:

```html
<script type="text/javascript" src="//cdnjs.cloudflare.com/ajax/libs/socket.io/1.3.6/socket.io.min.js"></script>
```

```javascript

var socket = io.connect("http://{}:{}".format(document.domain, location.port));
socket.on('connect', function(){
    socket.on('square', function(data){
        console.log(data.result);
        console.log(data.status);
    })
    socket.emit("square", {args: 2, kwargs: {}})
});

```

#### `async_method` decorator

The `async_method` decorator allows for asynchronous communication between server and client.
This is necessary in situations when you have a slow connection to the server, or
when server-side methods take a long time to run. My experience is that even with the
`Pyro4.futures` module, long-running server methods still tend to hang the client, especially
in the context of a Qt app.

Building a client/server that communicate asynchronously is not as simple as calling
server methods synchronously. First, the client has to be registered on the remote nameserver,
such that the server knows how to call client-side methods. Second, there has to be a means
of communicating to the server what methods it should call client-side. The
`async_method` decorator provides a single interface with which to do this that still
maintains a strict client/server separation (ie, the server doesn't know anything _a priori_
about the client's methods).

Let's say I wanted to make my `BasicServer.square` method asynchronous. I would do it server
side as follows:

```python
class BasicServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(name="BasicServer")

    @Pyro4.oneway
    @async_method
    def square(self, x):
        self.square.cb(x**2)
```

And client side, I'd have to do the following:

```python
from __future__ import print_function
import threading

import pyro4tunneling
import Pyro4

class BasicServerClient(object):

    def __init__(self, **kwargs):
        t = pyro4tunneling.Pyro4Tunnel(**kwargs)
        client = t.get_remote_object("BasicServer")
        # Now we have to register a daemon on the remote server
        cb_daemon = Pyro4.Daemon(host='localhost', port=50001)
        cb_daemon_thread = threading.Thread(target=cb_daemon.requestLoop)
        cb_daemon_thread.start()
        uri = cb_daemon.register(self, objectId="BasicServer.Client")
        existing = t.register_remote_daemon(cb_daemon)
        self.cb_daemon = cb_daemon

    def square_cb(self, results):
        print("square_cb: Called.")
        print("square_cb: {}".format(results))

if __name__ == '__main__':
    client = BasicServerClient(remote_server_name=""...)
    client.client.square(2, cb_info={"cb_handler":client,
                                    "cb":"square_cb"})

```

Of course, server side, you could subclass `Pyro4.Proxy` or even
`pyro_support.AutoReconnectingProxy` and then you wouldn't have to do the
awkward `client.client` business.
