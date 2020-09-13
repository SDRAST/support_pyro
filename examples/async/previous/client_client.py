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

import sys

from support.pyro import async

#@async.async_callback
def square_callback(res):
    print "square handler got:", res

#@async.async_callback
def repeat_callback(res):
    print "repeat handler got:", res

uri = "PYRO:BasicServer@localhost:9092"
proxy = async.AsyncProxy(uri)

print 'proxy.delayed_repeat returns:', proxy.delayed_repeat("hello", 10, callback=repeat_callback)
print 'proxy.delayed_square returns:', proxy.delayed_square(2,           callback=square_callback)
print 'proxy.delayed_simple returns:', proxy.simple('Hi!')

while True:
  try:
    pass
  except KeyboardInterrupt:
    sys.exit()

