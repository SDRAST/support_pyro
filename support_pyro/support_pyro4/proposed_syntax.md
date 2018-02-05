### Pyro4Server proposed syntax

I was thinking, and I thought it might be possible to create a Pyro4Server
decorator that added a few methods to any class so it could be run as a
server. Right now, syntax looks as follows:

```python
class Server(object):

    @Pyro4.expose
    def method(self, *args):
        return args # or whatever

server = Pyro4Server(cls=Server)
server.launch_server(tunnel_kwargs={"local":True})
```

This is all fine and dandy, but I might be able to play around with the syntax
and do the following:

```python

@Pyro4Server
class Server(object):

    def method(self, *args):
        return args

server = Server()
server.launch_server(tunnel_kwargs={"local":True})
```

Okay, this can be done. At this point I have to ask if it _should_ be done.
When I think about it, the former method of creating servers is more in line
with what goes on in Pyro4. The latter is sort of cool, but I think it is
ultimately bad for readability.
