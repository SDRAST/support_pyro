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

#<<<<<<< HEAD
#uri = "PYRO:Server@localhost:50001"
#
#client = AsyncProxy(uri)
#client.register(square_callback, repeat_callback)
#
#print("calling square")
#client.square(2, callback=square_callback)
#print("calling repeat")
#=======
uri = "PYRO:Server@localhost:50100"

client = async.AsyncProxy(uri)

#>>>>>>> 6ccd38c764ffada525eda2dc6792726707a33100
client.repeat("hello", 10, callback=repeat_callback)
client.square(2, callback=square_callback)

#<<<<<<< HEAD
# Because we're dealing with asynchronous responses, we need
# some sort of external event loop.
#while not (called["square_callback"] and called["repeat_callback"]):
#     pass
#
#=======
while not called["repeat_callback"] or not called["square_callback"]:
    pass
#>>>>>>> 6ccd38c764ffada525eda2dc6792726707a33100
