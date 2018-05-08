import logging

from support.pyro import async

called = {
    "square_callback":False,
    "repeat_callback":False
}

def square_callback(res):
    called["square_callback"] = True
    print(res)

def repeat_callback(res):
    called["repeat_callback"] = True
    print(res)

uri = "PYRO:BasicServer@localhost:9091"

client = async.AsyncProxy(uri)

client.repeat("hello", 10, callback=repeat_callback)
client.square(2, callback=square_callback)

while not called["repeat_callback"] or not called["square_callback"]:
    pass
