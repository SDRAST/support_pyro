import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "support_pyro",
    version = "1.3.0a",
    author = "TAMS team",
    author_email = "dean.shaff@gmail.com",
    description = ("Server and client extensions for pyro4tunneling"),
    install_requires=[
        'Pyro4'
    ],
    packages=["pyro_support"],
    keywords = ["Pyro4","server", "client", "pyro4tunneling"],
    url = "https://github.jpl.nasa.gov/dshaff/pyro-support"
    # data_files = [("", ["LICENSE"])]
)
