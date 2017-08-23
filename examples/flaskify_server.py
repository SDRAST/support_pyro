"""
flaskify_server.py

Example that shows how to use `flaskify` feature. This creates a flask app
using `exposed` methods of server.
"""
from pyro_support import Pyro4Server

def usage1():
    """
    Instantiate server separately and pass as first argument to
    Pyro4Server.flaskify classmethod
    """
    server = Pyro4Server(name="TestFlaskifyServer", simulated=True)
    app, _ = Pyro4Server.flaskify(server)
    app.run(debug=True)

def usage2():
    """
    Pass instantiation parameters directly to `flaskify` method
    """
    app, server = Pyro4Server.flaskify(name="TestFlaskifyServer",
                                       simulated=True)
    app.run(debug=True)

if __name__ == '__main__':
    usage1()
    # usage2()
