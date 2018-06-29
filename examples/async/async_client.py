import logging

try:
  from support.pyro import async
except:
  from support.pyro.support_pyro.support_pyro4.async.async_proxy import AsyncProxy
  
called = {
    "square_callback": False,
    "repeat_callback": False
}

def square_callback(res):
    called["square_callback"] = True
    print(res)

def repeat_callback(res):
    called["repeat_callback"] = True
    print(res)

uri = "PYRO:BasicServer@localhost:50100"

client = async.AsyncProxy(uri)

client.repeat("hello", 10, callback=repeat_callback)
client.square(2, callback=square_callback)

while not called["repeat_callback"] or not called["square_callback"]:
    pass

