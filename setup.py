import os
from setuptools import setup
from support_pyro import __version__

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "support_pyro",
    version = __version__,
    author = "TAMS team",
    author_email = "dean.shaff@gmail.com",
    description = ("Pyro4 and Pyro3 extensions."),
    long_descriptions = []
    install_requires=[
        'Pyro4'
    ],
    packages=["pyro_support"],
    keywords = ["Pyro4","server", "client", "pyro4tunneling"],
    url = "git@ra.jpl.nasa.gov:dshaff/support_pyro.git"
)
