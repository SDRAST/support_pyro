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

module_logger = logging.getLogger(__name__)

try:
    from support.trifeni import NameServerTunnel, DaemonTunnel, Pyro4Tunnel
except ImportError as err:
    module_logger.error("Can't import NameServerTunnel or TunnelError: {}".format(err))

from .configuration import config
from .async import EventEmitter

__all__ = ["Pyro4Server"]

class Pyro4Server(EventEmitter):
    """
    """
    def __init__(self, cls=None,
                       obj=None,
                       cls_args=None,
                       cls_kwargs=None,
                       name=None,
                       logfile=None,
                       logger=None,**kwargs):
        """
        Keyword Args:
        """
        super(Pyro4Server, self).__init__(**kwargs)
        if not logger: logger = logging.getLogger(module_logger.name +
                                                ".{}".format(self.__class__.__name__))
        self.logger = logger
        self.logger.debug("__init__: cls: {}".format(cls))
        if obj is None and cls is None:
            msg = "Need to provide either an object or a class to __init__"
            self.logger.error(msg)
            raise RuntimeError(msg)

        self.cls = None
        self.obj = None

        if obj is not None:
            self.obj = obj

        if cls is not None:
            self.cls = cls
            if cls_args is None: cls_args = ()
            if cls_kwargs is None: cls_kwargs = {}
            try:
                self.obj = self._instantiate_cls(cls, *cls_args, **cls_kwargs)
            except:
                pass

        if name is None: name = self.obj.__class__.__name__
        self._name = name
        self._logfile = logfile

        self._running = False
        self.tunnel = None
        self.tunnel_kwargs = None
        self.server_uri = None
        self.daemon_thread = None
        self.daemon = None
        self.threaded = False
        self.lock = threading.Lock()

    def _instantiate_cls(self, cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.obj = self._instantiate_cls(self.cls, *args, **kwargs)
        return (self, self.obj)

    @config.expose
    @property
    def logfile(self):
        return self._logfile

    @config.expose
    def running(self):
        with self.lock:
            return self._running

    @config.expose
    @property
    def name(self):
        return self._name

    @config.expose
    def ping(self):
        """
        ping the server
        """
        return "hello"

    def _handler(self, signum, frame):
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

    def launch_server(self, threaded=False, reverse=False,
                            objectId=None,objectPort=0,
                            objectHost="localhost",
                            local=True,
                            ns=True,tunnel_kwargs=None):
        """
        Launch server, remotely or locally. Assumes there is a nameserver registered on
        ns_host/ns_port.

        Keyword Args:

        Returns:
            dict: "daemon" (Pyro4.Daemon): The server's daemon
                  "thread" (threading.Thread or None): If threaded, a instance of threading.Thread
                    running the daemon's requestLoop. If not, None.
                  "uri" (Pyro4.URI): The daemon's uri
        """
        if tunnel_kwargs is None: tunnel_kwargs = {}
        daemon = Pyro4.Daemon(port=objectPort, host=objectHost)
        server_uri = daemon.register(self.obj,objectId=objectId)
        if not local:
            if ns:
                tunnel = NameServerTunnel(**tunnel_kwargs)
                tunnel.register_remote_daemon(daemon, reverse=reverse)
                tunnel.ns.register(self._name, server_uri)
            else:
                tunnel = Pyro4Tunnel(**tunnel_kwargs)
                tunnel.register_remote_daemon(daemon, reverse=reverse)

        else:
            tunnel = None
            if ns:
                ns = Pyro4.locateNS(**tunnel_kwargs)
                ns.register(self._name, server_uri)

        self.logger.info("{} available".format(server_uri))

        self.daemon = daemon
        self.tunnel_kwargs = tunnel_kwargs
        self.tunnel = tunnel
        self.server_uri = server_uri
        self.threaded = threaded

        with self.lock:
            self._running = True

        if not threaded:
            signal.signal(signal.SIGINT, self._handler)
            self.logger.debug("Starting request loop")
            self.daemon.requestLoop(self.running)
            return {"daemon":self.daemon, "thread":None, "uri":self.server_uri}
        else:
            t = threading.Thread(target=self.daemon.requestLoop, args=(self.running,))
            t.daemon = True
            t.start()
            return {"daemon":self.daemon, "thread":t, "uri":self.server_uri}

    def close(self):
        """
        Close down the server.
        If we're running this by itself, this gets called by the signal handler.
        """
        with self.lock:
            self._running = False
            try:
                self.daemon.unregister(self.obj)
            except Exception as err:
                self.logger.error("Couldn't unregister {} from daemon: {}".format(self.obj, err))

            if self.threaded:
                self.daemon.shutdown()
            else:
                self.daemon.close()

            if self.tunnel is not None:
                try:
                    self.tunnel.ns.remove(self._name)
                except AttributeError as err:
                    self.logger.debug("Tried to remove object from nameserver that we don't have reference to")
                except Pyro4.errors.ConnectionClosedError as err:
                    self.logger.debug("Connection to object already shutdown: {}".format(err))

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
                                # g = gevent.Greenlet.spawn(method, *args, **kwargs)
                                # status = "gevent.Greenlet started"
                                t = threading.Thread(target=method, args=args, kwargs=kwargs)
                                t.daemon = True
                                t.start()
                                status = "threading.Thread started"
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
    # server = Pyro4Server("TestServer", simulated=True)
    # server.launch_server(local=True, ns_port=9090, object_port=9091, obj_id="Pyro4Server.TestServer")
