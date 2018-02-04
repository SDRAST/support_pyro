import unittest
import logging
import threading

import Pyro4

def setup_logging(logger=None, logfile=None, logLevel=logging.DEBUG):

    logging.basicConfig(level=logLevel)
    if logger is None:
        logger = logging.getLogger("")

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

    logger.handlers = []
    logger.setLevel(logLevel)

    if logfile is not None:
        fh = logging.FileHandler(logfile)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logLevel)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    return logger
