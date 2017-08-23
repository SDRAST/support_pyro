# pyro4_server.py
from __future__ import print_function
import inspect
import logging
import os
import signal
import threading
import time
import datetime

import Pyro4
try:
    from pyro4tunneling import Pyro4Tunnel, TunnelError
except ImportError:
    from pyro4tunneling.pyro4tunnel import Pyro4Tunnel, TunnelError

from .configuration import config

__all__ = ["Pyro4Server","Pyro4ServerError"]

module_logger = logging.getLogger(__name__)

def blocking(func):
    """
    This decorator will make it such that the server can do
    nothing else while func is being called.
    """
    def wrapper(self, *args, **kwargs):
        lock = self.lock
        with lock:
            res = func(self, *args, **kwargs)
        return res
    return wrapper


def non_blocking(func):
    """
    Proceed as normal unless a functuon with the blocking
    decorator has already been called
    """
    def wrapper(self, *args, **kwargs):
        lock = self.lock
        while lock.locked():
            time.sleep(0.01)
        time.sleep(0.01)
        res = func(self, *args, **kwargs)
        return res

    return wrapper

class Pyro4ServerError(TunnelError):
    pass

class Pyro4Server(object):
    """
    A super class for Pyro4 servers. This class is meant to be subclassed.
    Attributes with a proceding underscore "_" are meant to be properties,
    accessible to any client.
    """
    def __init__(self, name="Pyro4Server", simulated=False, logfile=None):
        """
        Keyword Args:
            name (str): The name of the Pyro server.
            simulated (bool): Simulation mode bool
            local (bool): Local run bool
        """
        self._name = name
        self._simulated = simulated
        self._logfile = logfile
        self.logger = logging.getLogger(module_logger.name+"."+name)
        self.serverlog = self.logger # For compatibility
        self._local = None
        self._running = False

        self.tunnel = None
        self.remote_server_name = None
        self.remote_port = None
        self.proc = []
        self.server_uri = None
        self.daemon_thread = None
        self.daemon = None
        self.threaded = False
        self.lock = threading.Lock()

    @config.expose
    @property
    def logfile(self):
        return self._logfile

    @config.expose
    def running(self):
        self.logger.debug("running: Called.")
        with self.lock:
            return self._running

    @config.expose
    @property
    def name(self):
        return self._name

    @config.expose
    @property
    def locked(self):
        return self.lock.locked()

    @config.expose
    @property
    def simulated(self):
        """
        Is the server returning simulated (fake) data?
        """
        return self._simulated

    @config.expose
    @property
    def local(self):
        return self._local

    @config.expose
    def ping(self):
        """
        Method to call if one wants to test connection to server.
        If created a Pyro4.Proxy object using this server, one can also
        use the following snippet:

        ```python
        ns = Pyro4.locateNS()
        uri = ns.locate("<object_name>")
        p = Pyro4.Proxy(uri)
        p._pyroBind()
        ```
        Or use `p.ping()`, which will internally call `p._pyroBind` anyways.
        """
        return True

    def handler(self, signum, frame):
        """
        Define actions that should occur before the server
        is shut down.
        """
        try:
            self.logger.info("Closing down server.")
            self.close()
        except Exception as e:
            self.logger.error("Error shutting down daemon: {}".format(e), exc_info=True)
        finally:
            os.kill(os.getpid(), signal.SIGKILL)

    def launch_server(self, remote_server_name='localhost',
                            remote_port=22,
                            remote_username=None,
                            ns_host='localhost',
                            ns_port=9090,
                            obj_port=0,
                            obj_id=None,
                            local=True,
                            local_forwarding_port=None,
                            threaded=False,
                            reverse=False):
        """
        Launch server, remotely or locally. Assumes there is a nameserver registered on
        ns_host/ns_port.
        Keyword Args:
            remote_server_name (str): The host of remote server ("localhost")
                Note that even if this is "localhost" this does not mean
                that we're registering object on the local server.
                There could be a tunnel in place that uses "localhost".
            remote_port (int): The port by which to access remote server (22)
            remote_username (str): The username on the server on which we want to register object.
            ns_host (str): The namserver host on the remote server ("localhost")
            ns_port (int): The nameserver port on the remote server (9090)
            obj_port (int): The port on which to register object on remote nameserver (0)
            local (bool): Whether or not we're registering this object on a local name server.
                If this is true, then we act as if we're registering an object in the normal
                Pyro4 manner. (True)
            local_forwarding_port (int): The local forwarding port to use, if not the same as
                the one generated by Pyro4. (None)
            threaded (bool): Whether or not to run this independently or inside another program. (False)
            reverse (bool): Whether or not to create reverse tunnel, so we can access remotely registered
                object locally.
        """
        self.tunnel = Pyro4Tunnel(remote_server_name=remote_server_name,
                                    remote_username=remote_username,
                                    ns_host=ns_host,
                                    ns_port=ns_port,
                                    local=local,
                                    local_forwarding_port=local_forwarding_port)
        self.threaded = threaded
        self._local = self.tunnel.local

        self.daemon = Pyro4.Daemon(port=obj_port)
        self.tunnel.register_remote_daemon(self.daemon, reverse=reverse) # this sets up the tunnel
        self.server_uri = self.daemon.register(self,objectId=obj_id)
        self.logger.debug("Server uri is {}".format(self.server_uri))
        self.tunnel.ns.register(self._name, self.server_uri)
        self.logger.info("{} available".format(self._name))
        if not threaded:
            signal.signal(signal.SIGINT, self.handler)
        else:
            pass
        with self.lock:
            self._running = True
        self.logger.debug("Starting request loop")
        self.daemon.requestLoop(self.running)

    def close(self):
        """
        Close down the server.
        If we're running this by itself, this gets called by the signal handler.

        If we're running the server's daemon's requestLoop in a thread, then we
        might proceed as follows:

        ```
        s = PyroServer("CoolPyroServer")
        # The true argument is necessary so we don't attempt to call signal handler
        t = threading.Thread(target=s.connect, args=('localhost', 9090, True))
        t.start()
        # Do some other fresh stuff.
        s.close()
        t.join()
        ```
        """
        with self.lock:
            t0 = time.time()
            t1 = time.time()
            self._running = False
            self.daemon.unregister(self)
            # self.logger.debug("close: Took {:.3f} seconds to unregister daemon".format(time.time() - t1))
            # if we use daemon.close, this will hang forever in a thread.
            # This might appear to hang.
            t1 = time.time()
            if self.threaded:
                self.daemon.shutdown()
            else:
                self.daemon.close()
            # self.logger.debug("close: Took {:.3f} seconds to shutdown daemon".format(time.time() - t1))
            # remove the name/uri from the nameserver so we can't try to access
            # it later when there is no daemon running.
            t1 = time.time()
            try:
                self.tunnel.ns.remove(self._name)
            except Pyro4.errors.ConnectionClosedError as err:
                self.logger.debug("Connection to object already shutdown: {}".format(err))
            for proc in self.proc:
                proc.kill()
            # self.logger.debug("close: Took {:.3f} seconds to remove object from nameserver".format(time.time() - t1))
            self.logger.debug("close: Took {:.3f} seconds to run close method".format(time.time() - t0))

    @classmethod
    def flaskify(cls, *args, **kwargs):
        """
        Create a flask server using the PyroServer.
        There are two use cases:
        You pass parameters to instantiate a new instance of cls, or
        You pass an object of cls as the first argument, and this is the server used.
        """
        import json
        from flask import Flask, jsonify, request
        from flask_socketio import SocketIO, send, emit

        if len(args) > 0:
            if isinstance(args[0], cls):
                server = args[0]
        else:
            server = cls(*args, **kwargs)
        app = Flask(server.name)

        @app.route("/<method_name>", methods=['GET'])
        def method(data):
            try:
                get_data = json.loads(list(request.args.keys())[0])
            except json.decoder.JSONDecodeError:
                get_data = request.args
            args = get_data.get('args', ())
            kwargs = get_data.get('kwargs', {})
            if not (isinstance(args, list) or isinstance(args, tuple)):
                args = [args]
            if method_name in cls.__dict__:
                method = getattr(server, method_name)
                exposed = getattr(method, "_pyroExposed", None)
                if exposed:
                    status = "method {}._pyroExposed: {}".format(method_name, exposed)
                    try:
                        result = method(*args, **kwargs)
                    except Exception as err:
                        status = status + "\n" + str(err)
                        result = None
                else:
                    status = "method {} is not exposed".format(method_name)
                    result = None
            else:
                status = "method {} is not an server method".format(method_name)
                result = None
            print({"status":status, "result":result})
            return jsonify(data={"status":status, "result":result})

        return app, server

    @classmethod
    def flaskify_io(cls, *args, **kwargs):
        """
        Create a flaskio server using the PyroServer.
        There are two use cases:
        You pass parameters to instantiate a new instance of cls, or
        You pass an object of cls as the first argument, and this is the server used.
        """
        import json
        from flask import Flask, jsonify, request
        from flask_socketio import SocketIO, send, emit
        import gevent

        if len(args) > 0:
            if isinstance(args[0], cls):
                server = args[0]
        else:
            server = cls(*args, **kwargs)
        server.logger.info("Making flask socketio app.")
        app = Flask(server.name)
        app.config['SECRET_KEY'] = "radio_astronomy_is_cool"
        socketio = SocketIO(app)

        for method_pair in inspect.getmembers(cls):
            method_name = method_pair[0]
            method = getattr(server, method_name)
            exposed = getattr(method, "_pyroExposed", None)
            async = getattr(method, "_async_method", None)
            if exposed:
                server.logger.info("Registering method: {}".format(method_name))
                def wrapper(method, method_name):
                    def f(data):
                        args = data.get("args", [])
                        kwargs = data.get("kwargs", {})
                        async = getattr(method, "_async_method", None)
                        server.logger.info("{}: Async status: {}".format(method_name, async))
                        server.logger.info("{}: kwargs: {}".format(method_name, kwargs))
                        server.logger.info("{}: args: {}".format(method_name, args))
                        try:
                            if async:
                                kwargs['socket_info'] = {'app':app, 'socketio':socketio}
                                g = gevent.Greenlet.spawn(method, *args, **kwargs)
                                status = "gevent.Greenlet started"
                                result = None
                            else:
                                result = method(*args, **kwargs)
                                status = "success"
                        except Exception as err:
                            result = None
                            status = str(err)
                            server.logger.error(status)
                        with app.test_request_context("/"):
                            socketio.emit(method_name, {"status":status, "result":result})
                    return f

                socketio.on(method_name)(wrapper(method, method_name))

        return app, socketio, server

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # app, server = Pyro4Server.flaskify(name='TestServer', simulated=True)
    # app.run(debug=False)
    server = Pyro4Server("TestServer", simulated=True)
    server.launch_server(local=True, ns_port=9090, obj_port=9091, obj_id="Pyro4Server.TestServer")
