try:
    from .pyro3_util import *
except ImportError as err:
    if "Pyro" in str(err):
        pass
    else:
        print(err)
try:
    from .Pyro4.util import SerializerBase
    from .pyro4_util import Pyro4ObjectDiscoverer, arbitrary_tunnel, check_connection
    from .pyro4_server import Pyro4Server, Pyro4PublisherServer, Pyro4ServerError, blocking, non_blocking
    from .pyro4_client import Pyro4Client
except ImportError as err:
    # There are some virtualenvs where Pyro4 isn't installed.
    if "Pyro4" in str(err):
        pass
    else:
        print(err)
