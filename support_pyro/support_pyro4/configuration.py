import logging

import Pyro5

from .. import __version__ as pyro_support_version

module_logger = logging.getLogger(__name__)

class Configuration(object):
    """
    Configure pyro-support to be compatible with older versions of Pyro4.
    """
    def __init__(self):
        pyro4_version = Pyro4.__version__
        module_logger.debug("Using Pyro4 version {}".format(pyro4_version))
        if int(pyro4_version.split(".")[-1]) < 46:
            module_logger.debug("Creating dummy expose decorator for compatibility")
            def dummy_decorator(func):
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                return wrapper
            self.expose = dummy_decorator
        else:
            self.expose = Pyro4.expose

    def __str__(self):
        pyro4_version_str = "Pyro4 version: {}".format(Pyro4.__version__)
        pyro4_support_version_str = "pyro_support version: {}".format(pyro4_support_version)
        msg = "\n".join([pyro4_version, pyro4_support_version_str])
        return msg

config = Configuration()
