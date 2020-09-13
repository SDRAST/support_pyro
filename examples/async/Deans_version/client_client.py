"""
Example of using a Pyro4 proxy to use server methods

In this case the server instance (see 'plain_client.py') is replaced with a
proxy to a server instance.

The server must be running in another process. When a server method is called,
responses are handled by the function given as the 'callback' argument value.
The server may invoke the callback any number of times, as illustrated by
'async_server.py'.

An ordinary (non async) server method will return a result if the server method
is exposed. (See 'async_server.py')

Sample output:
  repeat returns: None
  square returns: None
  simple returns: Hi!
  repeat handler got: hello, hello, hello, hello, hello, hello, hello, hello, hello, hello
  square handler got: 4
  square handler got: (u'again:', 4)

"""
#import sys
import time

from support.pyro import async as async_pyro

#calls = {
#    "square_callback": 0,
#    "repeat_callback": 0
#}


def square_callback(res):
    print("client_client.square_callback: {}".format(res))
    #calls["square_callback"] += 1


def repeat_callback(res):
    print("client_client.repeat_callback: {}".format(res))
    #calls["repeat_callback"] += 1


uri = "PYRO:BasicServer@localhost:9092"
proxy = async_pyro.AsyncProxy(uri)

proxy.delayed_repeat("hello_1", 1, callback=repeat_callback)
proxy.delayed_square(2, callback=square_callback)


#def get_status():
#    return [calls["square_callback"] <= 3, calls["repeat_callback"] <= 4]


while True:
    time.sleep(0.0001)

time.sleep(0.1)
proxy._pyroRelease()
