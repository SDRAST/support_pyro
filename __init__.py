import logging

module_logger = logging.getLogger(__name__)

from .support_pyro import __version__
try:
    module_logger.debug("Doing from .support_pyro.support_pyro3 import *")
    from .support_pyro.support_pyro3 import *
except ImportError as err:
    module_logger.error("Couldn't import Pyro3 support: {}".format(err))
module_logger.debug("Doing from .support_pyro.support_pyro4 import *")
from .support_pyro.support_pyro4 import *
# for some reason these are not imported with '*'
from .support_pyro.support_pyro4 import zmq
from .support_pyro.support_pyro4 import async
