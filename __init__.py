import logging

module_logger = logging.getLogger(__name__)

from .support_pyro import __version__
try:
    from .support_pyro.support_pyro3 import *
except ImportError as err:
    module_logger.error("Couldn't import Pyro3 support: {}".format(err))
from .support_pyro.support_pyro4 import *
from .support_pyro.support_pyro4 import zmq
from .support_pyro.support_pyro4 import async
