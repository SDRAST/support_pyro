import threading

import zmq

__all__ = ["SocketWrapper"]

class SocketSafetyWrapper(object):

    def __init__(self, socket):
        self.socket = socket
        self.current_context = threading.current_thread()

    def __getattr__(self, attr):
        print("SocketSafetyWrapper.__getattr__: attr: {}, {},{}".format(attr, self.current_context, threading.current_thread()))
        return getattr(self.socket, attr)
