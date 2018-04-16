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
    class that can launch an object or instance of class on a nameserver or
    simply as a daemon.

    The flaskify method can automatically create flask routes from an object's
    methods

    The flaskify_io method can automatically create socket routes from an object's
    methods.

    Attributes:
        logger (logging.getLogger): object logger
        cls (type): a class whose methods and attribute the server accesses by
            instantiating an object.
        obj (object): An object whose methods and attributes the server accesses.
        name (str): Name of server
        logfile (str): Path to logfile for server.
        running (bool): boolean expressing whether the server has been launched
            or not
        tunnel (support.trifeni.Pyro4Tunnel like): A tunnel instance.
        tunnel_kwargs (dict): key word arguments that are uesd to instantiate
            tunnel instance
        server_uri (str/Pyro4.URI): the server's URI
        daemon_thread (threading.Thread): the thread in which the daemon's
            requestLoop method is running.
        daemon (Pyro4.Daemon): The server's daemon.
        threaded (bool): Whether or not the server is running in a thread or
            on the main thread.
        lock (threading.Lock): Lock for thread safety.
    """
    def __init__(self, cls=None,
                       obj=None,
                       cls_args=None,
                       cls_kwargs=None,
                       name=None,
                       logfile=None,
                       logger=None,**kwargs):
        """
        Args:
            kwargs: Passed to super class.
        Keyword Args:
            cls (type): A class that will be instantiated with cls_args
                cls_kwargs, to be used as the server's object.
            obj (object): Some object that will be registered on a Pyro4.Daemon.
            cls_args (tuple/list): Arguments passed to cls.
            cls_kwargs (dict): Keyword Arguments passed to cls.
            name (str): server name
            logfile (str): path to server's logfile
            logger (logging.getLogger): logging instance.
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
        """
        Create an instance of a class, given some arguments and keyword arguments.
        Args:
            cls (type): a class to be instantiated
            args: passed to cls
            kwargs: passed to cls
        """
        return cls(*args, **kwargs)

    # def __call__(self, *args, **kwargs):
    #     """
    #     DEPRECATED. For use when decorating classes with Pyro4Server class.
    #     """
    #     self.obj = self._instantiate_cls(self.cls, *args, **kwargs)
    #     return (self, self.obj)

    @config.expose
    @property
    def logfile(self):
        """
        Make logfile attribute accessible to a proxy corresponding to this server.
        """
        return self._logfile

    @config.expose
    def running(self):
        """
        Get running status of server
        """
        with self.lock:
            return self._running

    @config.expose
    @property
    def name(self):
        """
        Make name attribute accessible to a proxy.
        """
        return self._name

    @config.expose
    @name.setter
    def name(self, new_name):
        """
        Set name attribute.
        """
        self._name = new_name

    @config.expose
    def ping(self):
        """
        ping the server
        """
        return "hello"

    @config.expose
    def on(self, *args):
        """
        Explicitly expose EventEmitter's on method
        """
        super(Pyro4Server, self).on(*args)

    @config.expose
    def emit(self, *args):
        """
        Explicitly expose EventEmitter's emit method
        """
        super(Pyro4Server, self).emit(*args)

    def _handler(self, signum, frame):
        """
        Define actions that should occur before the server
        is shut down.
        Args:
            signum (int): current signal number
            frame (None/frame object): current stack frame
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
        Launch server, remotely or locally. Creates a Pyro4.Daemon, and optionally
        registers it on some local or remote nameserver.

        The if objectId, objectPort and objectHost are full specified, the daemon
        this method creates will look as follows:
            "PYRO:<objectId>@<objectHost>:<objectPort>"

        Keyword Args:
            threaded (bool): If true, launch server on a thread. Otherwise,
                launch server on main thread. (False)
            reverse (bool): Create revese tunnel. (False)
            objectId (str): The id for this object's daemon. (None)
            objectPort (int): The daemon's port. (0, or random)
            objectHost (str): The daemon's host. ("localhost")
            local (bool): Whether or not to create SSH tunnel to some remote
                server. If True, doesn't create tunnels. (True)
            ns (bool): Whether or not to attempt to register object's daemon
                on a nameserver (True)
            tunnel_kwargs (dict): used to create tunnel instance, or used
                as parameters to find nameserver (None)

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

        Args:
            args (list/tuple): If first argument is an object, then register
                this object's exposed methods. Otherwise, use args and kwargs
                as paramters to instantiate an object of implicit cls.
            kwargs (dict): Passed to implicit cls.
        Returns:
            app (Flask): Flask app
            server (object): some object whose methods/attributes have been
                registered as routes on app.
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
        Create a flaskio server.
        Use case is the same as Pyro4Server.flaskify, except that instead of
        registering an object's methods/attributes as routes, it registers
        them as socket routes.

        Args:
            args (list/tuple): If first argument is an object, then register
                this object's exposed methods. Otherwise, use args and kwargs
                as paramters to instantiate an object of implicit cls.
            kwargs (dict): Passed to implicit cls.
        Returns:
            app (Flask): Flask app
            socketio (SocketIO): flask_socketio.SocketIO instance.
            server (object): object whose methods have been registered as
                socket routes.
        """
        import json
        from flask import Flask, jsonify, request
        from flask_socketio import SocketIO, send, emit
        import eventlet
        eventlet.monkey_patch()

        if len(args) > 0:
            if isinstance(args[0], cls):
                server = args[0]
        else:
            server = cls(*args, **kwargs)
        server.logger.info("Making flask socketio app.")
        app = Flask(server.name)
        app.config['SECRET_KEY'] = "radio_astronomy_is_cool"
        socketio = SocketIO(app, async_mode="eventlet")

        for method_pair in inspect.getmembers(cls):
            method_name = method_pair[0]
            method = getattr(server, method_name)
            exposed = getattr(method, "_pyroExposed", None)
            async = getattr(method, "_pyroAsync", None)
            if exposed:
                server.logger.info("Registering method: {}, async: {}".format(method_name, async))
                def wrapper(method, method_name):
                    def inner(data):
                        args = data.get("args", [])
                        kwargs = data.get("kwargs", {})
                        async = getattr(method, "_pyroAsync", None)
                        # server.logger.debug("{}: async: {}".format(method_name, async))
                        # server.logger.debug("{}: kwargs: {}".format(method_name, kwargs))
                        # server.logger.debug("{}: args: {}".format(method_name, args))
                        try:
                            if async:
                                kwargs['socket_info'] = {'app':app, 'socketio':socketio}
                                g = eventlet.spawn_n(method, *args, **kwargs)
                                status = "eventlet.spawn_n started"
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
                    return inner

                # socketio.on(method_name)(wrapper(method, method_name))
                socketio.on_event(method_name, wrapper(method, method_name))

        return app, socketio, server

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # app, server = Pyro4Server.flaskify(name='TestServer', simulated=True)
    # app.run(debug=False)
    # server = Pyro4Server("TestServer", simulated=True)
    # server.launch_server(local=True, ns_port=9090, object_port=9091, obj_id="Pyro4Server.TestServer")
