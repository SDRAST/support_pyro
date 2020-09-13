import socket
from Pyro5.api import SerializerBase

def socket_error_class_to_dict(obj):
    """Dictionary representation of socket.error"""
    return {
        "__class__": "socket.error"
    }


def socket_error_dict_to_class(classname, *args):
    """Reconstruct socket.error"""
    return socket.error(*args)


def register_socket_error():
    """
    Register socket.error to Pyro4's SerializerBase so we can send
    socket.errors across Pyro4 connections.
    """
    SerializerBase.register_dict_to_class(
        "socket.error", socket_error_dict_to_class)
    SerializerBase.register_class_to_dict(
        socket.error, socket_error_class_to_dict)
