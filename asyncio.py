import asyncio
import logging
import Pyro5.api
import queue
import sys
import threading

logger = logging.getLogger(__name__)

import MonitorControl.BackEnds.ROACH1.simulator as ROACH1

class CallbackReceiver(object):
  """
  Class passed to remote server to handle the data transfer
  
  The class can be initialized with a queue to get the data.  If not provided,
  it will create its own queue.
  """
  def __init__(self, parent=None):
    """
    Initialize the receiver with a queue on which the server puts the data
    
    Args
    ====
      parent - the object of which this is an attribute
    """
    self.parent = parent
    self.logger = logging.getLogger(logger.name+".CallbackReceiver")
    self.queue = queue.Queue()
    self.daemon = Pyro5.api.Daemon()
    self.uri = self.daemon.register(self)
    self.lock = threading.Lock()
    with self.lock:
            self._running = True
  
    self.thread = threading.Thread(target=self.daemon.requestLoop, 
                                   args=(self.running,) )
    self.thread.daemon = True
    self.thread.start()    

  @Pyro5.api.expose
  def running(self):
    """
    Get running status of server
    """
    with self.lock:
      return self._running
  
  @Pyro5.api.expose
  @Pyro5.api.callback
  def finished(self, msg):
    """
    Method used by the remote server to return the data
    
    Parent must have a thread waiting to do queue.get()
    
    Because this runs in the server namespace, no logging is possible.
    """
    self.queue.put(msg) # server puts data on the queue
    

if __name__ == "__main__":
  logging.basicConfig()
  mainlogger = logging.getLogger()
  mainlogger.setLevel(logging.DEBUG)
    
  be = ROACH1.SAOspecServer('test')
  cb_receiver = CallbackReceiver()
  be.start(n_accums=3, integration_time=3, callback=cb_receiver)

