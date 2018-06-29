# -*- coding: utf-8 -*-
"""
Functions to set up Pyro using tunnels if necessary.

The module keeps track of the tunnels it creates.  A call to
'cleanup_tunnels()' should be made before ending the program.
"""
import Pyro
import Pyro.core
import Pyro.naming
import Pyro.errors
import time
import logging
import numpy
import os
import atexit
import socket
import sys

from local_dirs import *
from support import NamedClass
from support.local_dirs import log_dir
from support.logs import (
    set_module_loggers,
    initiate_option_parser,
    init_logging,
    get_loglevel,
    set_loglevel
)
from support.network import get_domain, get_local_network
import support.tunneling as T

# Set up Pyro system logging
NONE = 0
ERRORS = 1
WARNINGS = 2
ALL = 3
Pyro.config.PYRO_TRACELEVEL = WARNINGS
Pyro.config.PYRO_STDLOGGING = True
SLog = Pyro.util.SystemLogger()

# Set up Python logging
logging.basicConfig(level=logging.WARNING)
module_logger = logging.getLogger(__name__)

try:
  pyro_log_dir = os.path.join(log_dir, "PYRO")
  if not os.path.exists(pyro_log_dir):
    os.makedirs(pyro_log_dir)
except OSError as err:
  pass
  # module_logger.error("Couldn't create {}".format(pyro_log_dir))

nameserver = None

__all__ = [
    "PyroServer", "PyroServerLauncher",
    "PyroTaskClient", "NameserverResource",
    "pyro_server_request", "pyro_server_details",
    "cleanup_tunnels", "get_nameserver", "get_device_server",
    "launch_server", "pyro_server_name", "full_name", "nameserver"
]


class PyroServer(Pyro.core.ObjBase):
  """
  Superclass for Pyro servers

  Public Attributes::
    logger - logging.Logger object
    run    - True if server is running
  """
  def __init__(self):
    """
    """
    Pyro.core.ObjBase.__init__(self)
    self.logger = logging.getLogger(module_logger.name+".MCserver")
    self.logger.debug("__init__: logger is %s",self.logger.name)
    self.run = True

  def sanitize(self, list_or_dict):
    """
    Pyro cannot return objects whose class is not known by the client.

    Any standard types of objects are returned as is.  A list or a dict,
    however, needs to be examined item by item to see if they are
    standard types.  Those that aren't need to be replaced with a string
    representation.
    """
    if type(list_or_dict) == str or \
       type(list_or_dict) == int or \
       type(list_or_dict) == float or \
       type(list_or_dict) == bool:
      return list_or_dict
    elif type(list_or_dict) == list:
      newlist = []
      for item in list_or_dict:
        newlist.append(self.sanitize(item))
      return newlist
    elif type(list_or_dict) == dict:
      newdict = {}
      for key in list_or_dict.keys():
        newdict[key] = self.sanitize(list_or_dict[key])
      return newdict
    else:
      return str(list_or_dict)

  def request(self,request):
    """
    Evaluate a statement in the local context

    Note that this only returns strings or standard types, not the user
    defined objects on the server side which they may represent.

    Examples (from the client side):
    >>> ks.request("self.spec[0].LO.get_p('frequency')")
    1300.0
    >>> ks.request("self.IFsw[3].state")
    8

    @param request : command to be evaluated
    @type  request : str

    @return: response
    """
    self.logger.debug("request: processing: %s", request)
    response = eval(request)
    self.logger.debug("request: response was: %s",response)
    if type(response) == str or \
       type(response) == int or \
       type(response) == float or \
       type(response) == bool or \
       type(response) == numpy.ndarray :
      self.logger.debug("request: returns native object")
      return response
    elif type(response) == list or type(response) == dict:
      Pyro_OK = self.sanitize(response)
      self.logger.debug("request: sanitized list or dict %s",Pyro_OK)
      return Pyro_OK
    else:
      self.logger.debug("request: returns str")
      return str(response)

  # ==================== Methods for managing the server ====================

  def running(self):
    """
    Report if the manager is running.

    Attribute run may be set to False by a sub-class
    """
    return self.run

  def halt(self):
    """
    Command to halt the manager
    """
    self.logger.info("halt: Halting")
    self.run = False

class PyroServerLauncher(object):
  """
  Class to create Pyro daemons which can be linked to Pyro servers

  Pyro servers are sub-classes of Pyro.core.ObjBase.  They are linked to
  Pyro daemons and then published by a Pyro namserver.
  """
  def __init__(self, name, nameserver_host='dto'):
    """
    Create a PyroServerLauncher() object.

    If a nameserver host is not given then a nameserver is selected according
    the domain of the local host. TO DO: allow a different nameserver host at
    each Complex.

    @param name : name to be used for logging
    @type  name : str

    @param nameserver_host : host where the Pyro nameserver resides
    @type  nameserver_host : str
    """
    self.name = name
    self.logger = logging.getLogger(module_logger.name+".PyroServerLauncher")
    self.logger.debug(" Initiating PyroServerLauncher for %s", nameserver_host)

    self._start_Pyro_log()

    if nameserver_host == None:
      domain = get_domain(get_local_network())
      if domain == 'fltops':
        nameserver_host = 'crux'
      elif domain == 'jpl':
        nameserver_host = 'dto'
      else:
        raise RuntimeError("domain %s has no Pyro nameserver", domain)
    self.logger.debug(" %s creating daemon", self.name)
    self._create_daemon(nameserver_host)
    # our nameserver is now self.ns.
    self.logger.debug(" %s initialized", self.name)

  def _start_Pyro_log(self):
    """
    """
    Pyro.config.PYRO_LOGFILE = log_dir+'/PYRO/'+self.name+'.log'
    SLog.msg(self.name,"pyro_support module imported")
    SLog.msg(self.name,"server started")

  def _create_daemon(self, nameserver_host):
    """
    Create the server daemon.

    The nameserver host may be behind a firewall, in which case a tunnel is
    created to it.

    @param nameserver_host : the host where the nameserver resides
    @type  nameserver_host : str
    """
    def _connect_to_pyro_nameserver(server):
      """
      This either accesses the Pyro nameserver directly or tunnels to it.

      If a tunnel is necessary, the tunnel endpoint is also assumed to be
      the nameserver.

      @param server : nameserver short name
      @type  server : str

      @return: pyro_host (str), pyro_port (int)
      """
      self.logger.debug("_connect_to_pyro_nameserver: invoked")
      if T.need_tunnel(full_name[server]) == False:
        self.logger.debug("_connect_to_pyro_nameserver: no tunnel is needed")
        pyro_host = server
        pyro_port = 9090
      else:
        self.logger.debug("_connect_to_pyro_nameserver: need a tunnel to JPL")
        # create a tunnel to the nameserver
        troach = T.Tunnel(server)
        pyro_host = 'localhost'
        pyro_port = T.free_socket()
        self.logger.info("_connect_to_pyro_nameserver: we have a tunnel")
        self.logger.info("_connect_to_pyro_nameserver: we have proxy port at",
                         pyro_port)
        # Is the following used at all?
        p = T.makePortProxy(server, pyro_port, server, 9090)
      return pyro_host, pyro_port

    self.logger.debug("_create_daemon: entered")
    self.pyro_host, self.pyro_port = _connect_to_pyro_nameserver(nameserver_host)
    self.logger.debug('_create_daemon: %s using host %s and port %d',
                  self.name, self.pyro_host, self.pyro_port)
    # Find a nameserver:
    #   1. get the name server locator
    self.locator = Pyro.naming.NameServerLocator()
    #   2. locate the name server
    self.ns = self.locator.getNS(host=self.pyro_host, port=self.pyro_port)
    # Create a daemon
    self.daemon = Pyro.core.Daemon(port=T.free_socket())
    # Get the daemon socket; is this necessary?
    host, port = self.daemon.sock.getsockname()
    self.logger.debug('_create_daemon: The pyro deamon is running on port %d',
                      port)
    self.daemon.useNameServer(self.ns)

  def start(self, server):
    """
    Starts the server running.

    @param server : the Pyro task server object
    @type  server : instance of subclass of Pyro.core.ObjBase

    @param pyroServerName : the name by which the server object is known
    @type  pyroServerName : str
    """
    self.server = server
    try:
      uri=self.daemon.connect(server, self.name)
    except Pyro.errors.NamingError as details:
      self.logger.error(
        "start: could not connect server object to Pyro daemon. %s already exists",
        str(details[1]), exc_info=True)
      raise Exception("Cannot connect server to daemon.")
    else:
      # Servers advertised
      self.logger.debug("start: nameserver database: %s",self.ns.flatlist())
      try:
        self.daemon.requestLoop(condition=self.server.running)
      except KeyboardInterrupt:
        self.logger.warning("start: keyboard interrupt")
      finally:
        self.logger.info("start: request loop exited")
        self.daemon.shutdown(True)
      self.logger.info("start: daemon done")

  def halt(self):
    """
    """
    self.daemon.shutdown(True)
    SLog.msg(self.name,"server stopped")

  def finish(self):
    """
    """
    self.logger.info("%s ending", self.name)
    # nameservers are volatile so we need to get another instance
    try:
      ns = self.locator.getNS(host=self.pyro_host)
    except Pyro.errors.NamingError:
      self.logger.error("""If pyro-ns is not running. Do 'pyro-ns &'""")
      raise RuntimeError("No Pyro nameserver")
    try:
      ns.unregister(self.name)
    except Pyro.errors.NamingError:
      self.logger.debug("%s was already unregistered", self.name)
    self.logger.info("%s finished", self.name)


class PyroTaskClient(Pyro.core.DynamicProxy):
  """
  Superclass for clients of Pyro tasks

  This creates a DynamicProxy.  It also creates a temporary nameserver
  client which goes away after the initialization.

  Pulic attributes::
   ns -          Pyro nameserver object used by client
   server -      Pyro remote task server object
   server_host - host which has the remote task server
   server_port - port on remote host used by server
  """
  def __init__(self, servername, pyro_ns = "dto", pyro_port = 9090):
    """
    Create an instance of a Pyro task client

    @param servername : Pyro name of the remote task server
    @type  servername : str

    @param pyro_ns : name of the Pyro nameserver host
    @type  pyro_ns : str

    @param pyro_port : port used by the Pyro nameserver
    @type  pyro_port : int
    """
    self.logger = logging.getLogger(module_logger.name+".PyroTaskClient")
    nsr =  NameserverResource()
    if nsr:
      self.logger.debug(" nameserver object is %s",str(nsr.ns))
      server = nsr.ns.resolve(servername)
      server_host, server_port = pyro_server_details(
        pyro_server_name[server.address], server.port)
      device_request = \
        "PYROLOC://" + server_host + ":" + str(server_port) + \
        "/" + servername
      self.logger.debug(" proxy request: %s",device_request)
      try:
        Pyro.core.DynamicProxy.__init__(self, device_request)
      except Pyro.errors.NamingError:
        self.logger.error(" pyro name error", exc_info=True)
        raise Exception("Connecting to Pyro nameserver failed")
      except Exception:
        self.logger.error(" request for server connection failed",
                            exc_info=True)
        raise Exception("Connecting to Pyro nameserver failed")
      else:
        # Give connection time to be established
        time.sleep(2)
      self.logger.debug(" dynamicProxy instantiated.")

class NameserverResource:
  """
  """
  def __enter__(self, pyro_ns = "dto", pyro_port = 9090):
    """
    """
    self.logger = logging.getLogger(module_logger.name+".NameserverResource")

    class PyroNameserver:
      """
      """
      def __init__(self,pyro_ns="dto", pyro_port = 9090):
        self.logger = logging.getLogger(
                            module_logger+".NameserverResource.PyroNameserver")
        self.tunnels = []
        # Find a nameserver:
        self.logger.debug(
          " Requested PyroNameserver host is %s using port %d",
          pyro_ns,pyro_port)
        # This will create a tunnel to the nameserver if needed
        pyro_ns_host, ns_proxy_port = self._pyro_server_details(pyro_ns,
                                                                pyro_port)
        self.logger.debug(" Real nameserver is %s using port %d",
                            pyro_ns_host, ns_proxy_port)
        # 1. get a non-persistent name server locator
        locator = Pyro.naming.NameServerLocator()
        # 2. locate the name server
        self.ns  = pyro_server_request(locator.getNS,
                                       host=pyro_ns_host,
                                       port=ns_proxy_port)
        if self.ns == None:
          self.logger.error("No nameserver connection")
          raise RuntimeError("No nameserver connection")

      def _pyro_server_details(self, ns_shortname, pyro_ns_port):
        """
        Provides the hostname and port where the Pyro server appears.

        The hostname and port will be the obvious ones if the client is in the
        same domain.  Otherwise, the server will appear at a tunnel port on the
        localhost.

        @param ns_shortname : Pyro nameserver short host name (without domain)
        @type  ns_shortname : str

        @param pyro_ns_port : Pyro nameserver port, typically 9090
        @type  pyro_ns_port : int

        @return: (apparent_host [str], apparent port [int])
        """
        if T.need_tunnel(full_name[ns_shortname]) == False:
          # no proxy port
          if ns_shortname == "localhost":
            pyro_ns_host = ns_shortname
          else:
            pyro_ns_host = full_name[ns_shortname]
          ns_proxy_port = pyro_ns_port
        else:
          # we need a tunnel to the Pyro nameserver
          nameserver_tunnel = T.Tunnel(ns_shortname)
          self_logger.debug(
                       "_pyro_server_details: NameserverResource has a tunnel")
          ns_proxy_port = T.free_socket()
          self.logger.debug(
                "_pyro_server_details: Pyro nameserver has a proxy port at %d",
                              ns_proxy_port)
          ns_tunnel_process = T.makePortProxy(ns_shortname,
                                              ns_proxy_port,
                                              IP[ns_shortname],
                                              pyro_ns_port)
          self.tunnels.append(ns_tunnel_process)
          self.logger.debug("_pyro_server_details: Tunnels for %s: %s",
                                                        str(self),self.tunnels)
          pyro_ns_host = 'localhost'
          self.logger.debug("_pyto_server_details: process ID is %d",
                            ns_tunnel_process.pid)
        return pyro_ns_host, ns_proxy_port

      def __enter__(self):
        return self

      def _cleanup(self):
        """
        """
        self.logger.debug("_cleanup: called for %s",self.tunnels)
        for task in self.tunnels:
          self.logger.info("_cleanup: %d killed",task.pid)
          task.terminate()
          self.tunnels.remove(task)
          self.logger.debug(
                    "_cleanup: %s removed from NameserverResource tunnel list",
                    str(task))

    self.nameserver_obj = PyroNameserver(pyro_ns = pyro_ns,
                                         pyro_port = pyro_port)
    return self.nameserver_obj

  def __exit__(self, type, value, traceback):
    """
    """
    self.logger.debug("__exit__() called")
    self.nameserver_obj._cleanup()

# --------------------------- module methods -------------------------------

def pyro_server_request(task, *args, **kwargs):
  """
  Make a request of a Pyro server

  Since it can take a while to set up a tunnel to a Pyro server, the
  first request of the server should be repeated until successful or until
  it times out.

  Note
  ====
  Timing out still to be implemented

  @param task : the function requested
  @type  task : a method instance

  @param args : positional arguments expected by task

  @param kwargs : keyword arguments expected by task

  @return: result of the requested task
  """
  if kwargs.has_key('timeout') == False:
    timeout=10.
  result = None
  while timeout > 0:
    try:
      result = task(*args, **kwargs)
    except Pyro.errors.ProtocolError as details:
      module_logger.warning("pyro_server_request: %s (%f sec left)",
                       details,timeout)
      if str(details) == "connection failed":
        timeout -= 0.5
        time.sleep(0.5)
    else:
      timeout = 0.
  return result

def pyro_server_details(ns_shortname, pyro_ns_port):
  """
  Provides the hostname and port where the Pyro server appears.

  The hostname and port will be the obvious ones if the client is in the
  same domain.  Otherwise, the server will appear at a tunnel port on the
  localhost.

  @param ns_shortname : Pyro nameserver short host name (without domain)
  @type  ns_shortname : str

  @param pyro_ns_port : Pyro nameserver port, typically 9090
  @type  pyro_ns_port : int

  @return: (apparent_host [str], apparent port [int])
  """
  global tunnels

  if T.need_tunnel(full_name[ns_shortname]) == False:
    # no proxy port
    ns_proxy_port = pyro_ns_port
    if ns_shortname == "localhost":
      module_logger.debug("pyro_server_details: ns is at a localhost port")
      pyro_ns_host = ns_shortname
    else:
      pyro_ns_host = full_name[ns_shortname]
    ns_proxy_port = pyro_ns_port
  else:
    module_logger.debug("pyro_server_details: ns is not at JPL")
    # we need a tunnel to the Pyro nameserver
    module_logger.debug("pyro_server_details: requesting a tunnel")
    nameserver_tunnel = T.Tunnel(ns_shortname)
    module_logger.debug("pyro_server_details: module has a tunnel")
    ns_proxy_port = T.free_socket()
    module_logger.debug("pyro_server details: Pyro server proxy port is at %d",
                  ns_proxy_port)
    ns_tunnel_process = T.makePortProxy(ns_shortname,
                                        ns_proxy_port,
                                        IP[ns_shortname],
                                        pyro_ns_port)
    tunnels.append(ns_tunnel_process)
    pyro_ns_host = 'localhost'
    module_logger.debug("pyro_server_details: Tunnel process ID is %d",
                        ns_tunnel_process.pid)
  module_logger.debug("pyro_server_details: server is %s:%s",
    pyro_ns_host, ns_proxy_port)
  return pyro_ns_host, ns_proxy_port

def cleanup_tunnels():
  """
  Remove tunnels that were created for this session
  """
  global tunnels
  module_logger.debug("Open tunnel tasks: %s",str(tunnels))
  for task in tunnels:
    module_logger.info("%d killed",task.pid)
    task.kill()

# This is only used by get_device_server
def get_nameserver(pyro_ns = "dto", pyro_port = 9090):
  """
  Get a Pyro non-persistent nameserver object.

  Note that the nameserver object loses its connection to the server if it
  is not used for a while.  If this might happen, test for a
  Pyro.errors.NamingError exception and, if necessary, call this method
  again.

  Examples of what you might do with it::
   In [5]: from support.pyro import get_nameserver
   In [6]: ns = get_nameserver()
   In [7]: ns.flatlist()
   Out[7]:
   [(':Pyro.NameServer',
    <PyroURI 'PYRO://128.149.22.108:9090/8095166c0d501fbe708a6e1d7bb6cf39b8'>),
   (':Default.kurtspec_server',
    <PyroURI 'PYRO://128.149.22.108:29052/8095166c1e751fbff7c27dd4bb93c186f4'>)]
   In [8]: ns.fullName('kurtspec_server')
   Out[8]: ':Default.kurtspec_server'
   In [9]: ns.unregister('kurtspec_server')

  @param pyro_ns : the host where the Pyro nameserver resides
  @type  pyro_ns : str

  @param pyro_port : the port used by the Pyro name server
  @type  pyro_port : int

  @return: Pyro nameserver object
  """
  global nameserver
  # if necessary, create a tunnel to the nameserver
  module_logger.debug("get_nameserver: try at %s:%d", pyro_ns, pyro_port)
  pyro_ns_host, ns_proxy_port = pyro_server_details(pyro_ns, pyro_port)
  module_logger.debug("get_nameserver: nameserver host is %s:%d", pyro_ns_host,
                         ns_proxy_port)
  # Find a nameserver:
  # 1. get a non-persistent name server locator
  locator = Pyro.naming.NameServerLocator()
  # 2. locate the name server
  module_logger.debug("get_nameserver: have locator; requesting a nameserver")
  ns  = pyro_server_request(locator.getNS,
                            host=pyro_ns_host,
                            port=ns_proxy_port)
  module_logger.debug("get_nameserver: ns is %s", ns)
  if ns == None:
    module_logger.error("get_nameserver: no nameserver connection")
    raise RuntimeError("No nameserver connection")
  else:
    nameserver = ns
    return ns

def get_device_server(servername, pyro_ns = "dto", pyro_port = 9090):
  """
  Establishes a connection to a Pyro device server.

  This is for Python command-line use, as in this example::
    In [5]: from Observatory.pyro_support import get_device_server
    In [6]: mgr = get_device_server('MMS_manager')
  If the server is behind a firewall, a tunnel is created.

  @param servername : the name as it appears in a 'pyro-nsc list' response
  @type  servername : str

  @param pyro_ns : the host where the Pyro nameserver resides
  @type  pyro_ns : str

  @param pyro_port : the port used by the Pyro name server
  @type  pyro_port : int

  @return:
  """
  global namserver
  if nameserver:
    ns = nameserver
  else:
    ns = get_nameserver(pyro_ns, pyro_port)
  module_logger.debug("get_device_server: nameserver is %s", ns)
  # Find the device server
  server = ns.resolve(servername)
  module_logger.debug("get_device_server: device server is at %s:%d", server.address,
                                                         server.port)
  # Is this the localhost?
  if server.address == socket.gethostbyname(socket.gethostname()):
    server.address = socket.gethostbyname('localhost')
  server_host,server_port = pyro_server_details(pyro_server_name[server.address],
                                                            server.port)
  try:
    device_request = "PYROLOC://" + server_host + ":" + str(server_port) + \
                     "/"+servername
    module_logger.debug("get_device_server: proxy request: %s",device_request)
    device = Pyro.core.DynamicProxy(device_request)
    module_logger.debug("get_device_server: returns %s", device)
  except Pyro.errors.NamingError as details:
    module_logger.error("get_device_server: Pyro name error: %s: %s",
                        details[0],details[1])
    return [None, "get_device_server: Pyro name error", str(details)]
  except Exception as details:
    module_logger.error("get_device_server: Request for server connection failed\n%s",
                        details)
    return [None,"Request for server connection failed",str(details)]
  else:
    return device

def launch_server(serverhost, taskname, task):
  """
  Combines a device controller class with a Pyro class

  This seems not to be in use anymore.  Use the PyroServerLauncher class
  """
  # create the server launcher
  module_logger.debug(" Launching Pyro task server %s on %s",
                      taskname, serverhost)
  server_launcher = PyroServerLauncher(taskname, serverhost) #, taskname)

  # check to see if the server is running already.
  response = server_launcher.ns.flatlist()
  no_conflict = True
  for item in response:
    if item[0].split('.')[1] == taskname:
      no_conflict = False
      break
  if no_conflict:
    # launch and publish the task server.  This starts the event loop.
    module_logger.info(" Starting the server...")
    server_launcher.start(task) # ,taskname)
  else:
    module_logger.error(
      "launch_server: %s is already published.  Is the server already running?",
      taskname)
    module_logger.error(
                      "               If not, do 'pyro-nsc remove %s'",taskname)
    raise RuntimeError("Task is already registered")


# Generally, JPL/DSN hosts cannot be resolved by DNS
GATEWAY, IP, PORT = T.make_port_dict()
pyro_server_name = {'127.0.0.1':      'localhost',
                    '128.149.22.95':  'roachnest',
                    '137.228.236.103': 'dto',
                    '137.228.236.70': 'rac13b',
                    '137.228.246.31': 'wbdc',
                    '137.228.246.38': 'tpr',
                    '137.228.246.57': 'crux',
                    '137.228.246.105':'krx43'}
full_name = {'crux':      'crux.cdscc.fltops.jpl.nasa.gov',
             'dto':       'dto1.gdscc.fltops.jpl.nasa.gov',
             'krx43':     'K2R43.cdscc.fltops.jpl.nasa.gov',
             'localhost': 'localhost',
             'rac13b':    'venus-rac3.gdscc.fltops.jpl.nasa.gov',
             'tpr':       'dss43tpr1.cdscc.fltops.jpl.nasa.gov',
             'wbdc':      'dss43wbdc2.cdscc.fltops.jpl.nasa.gov',
             'roachnest': 'roachnest.jpl.nasa.gov'}

# Remember any tunnels that may be opened
tunnels = []
atexit.register(cleanup_tunnels)

if __name__ == "__main__":

  examples = """This command::

    In [1]: run pyro.py

  will launch a very simple server::

    kuiper@dto:~$ pyro-nsc list
    Locator: searching Pyro Name Server...
    NS is at 128.149.22.108 (dto.jpl.nasa.gov) port 9090
    :Default --> ( TestServer )

  which can be checked this way.  To check for name conflict before launching
  a server us::

  """

  class ServerTask(NamedClass):
    """
    """
    def __init__(self):
      self.logger = logging.getLogger(module_logger.name+".ServerTask")
      self.name = "TestServer"
      super(ServerTask,self).__init__()
      self.logger.debug(" instantiated")

  class TestServerClass(PyroServer, ServerTask):
    """
    """
    def __init__(self):
      """
      """
      self.logger = logging.getLogger(module_logger.name+".TestServerClass")
      super(TestServerClass,self).__init__()
      self.logger.debug(" superclass initialized")
      #ServerTask.__init__(self)
      self.logger.debug(" server instantiated")
      self.run = True

  def main():
    """
    """
    p = initiate_option_parser(
     """Generic Pyro server which servers as a template for actual servers.""",
     examples)
    # Add other options here

    opts, args = p.parse_args(sys.argv[1:])

    # This cannot be delegated to another module or class
    mylogger = init_logging(logging.getLogger(),
                            loglevel   = get_loglevel(opts.file_loglevel),
                            consolevel = get_loglevel(opts.stderr_loglevel),
                            logname    = opts.logpath+__name__+".log")
    mylogger.debug(" Handlers: %s", mylogger.handlers)
    loggers = set_module_loggers(eval(opts.modloglevels))

    psl = PyroServerLauncher("TestServer", nameserver_host='dto')
    m = TestServerClass()
    psl.start(m)

    psl.finish()

  main()
