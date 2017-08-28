import time

from .pyro4_server import Pyro4Server
from .util import PausableThread, iterative_run, AsyncCallback

class PublisherThread(PausableThread):
    """
    A Pausable Thread that will publish data to any registered callbacks,
    given some data_cb callback function.
    The run function calls the data_cb function, and then calls all registered callbacks.
    To improve performance,
    """
    def __init__(self,
                update_rate,
                data_cb,
                data_cb_args=None,
                data_cb_kwargs=None,
                cb_info=None,
                socket_info=None,
                **kwargs):

        PausableThread.__init__(self, **kwargs)
        self.update_rate = update_rate
        self.data_cb = data_cb

        if not data_cb_args: self.data_cb_args = ()
        if not data_cb_kwargs: self.data_cb_kwargs = {}

        if cb_info:
            if not isinstance(cb_info, list):
                self.cb_info = [cb_info]
            else:
                self.cb_info = cb_info
            for i, info in enumerate(self.cb_info):
                if isinstance(info, AsyncCallback):
                    self.cb_info[i] = info
                elif isinstance(info, dict):
                    self.cb_info[i] = AsyncCallback(cb_info=info, socket_info=socket_info)
        else:
            self.cb_info = []

    @iterative_run
    def run(self):
        data = self.data_cb(*self.data_cb_args,**self.data_cb_kwargs)
        for cb in self.cb_info:
            cb.cb(data)
        time.sleep(self.update_rate)

    def register_callback(self, cb_info, socket_info=None):
        """
        Register some callback with the Publisher.
        args:
            cb_info (dict):
        """
        with self._lock:
            if isinstance(cb_info, AsyncCallback):
                self.cb_info.append(cb_info)
            elif isinstance(cb_info, dict):
                self.cb_info.append(AsyncCallback(cb_info=cb_info, socket_info=socket_info))

    def change_rate(self, new_rate):
        """
        Change the rate at which the publisher updates.
        Args:
            new_rate (float): Time in seconds to wait before calling self.data_cb
        """
        with self._lock:
            self.update_rate = new_rate


class Pyro4PublisherServer(Pyro4Server):
    """
    """
    def __init__(self, **kwargs):
        """
        """
        Pyro4Server.__init__(self, **kwargs)
        self.publisher_thread = None

    def start_publishing(self):
        raise NotImplementedError("start_publishing method not implemented.")

    def pause_publishing(self):
        raise NotImplementedError("pause_publishing method not implemented.")

    def stop_publishing(self):
        raise NotImplementedError("stop_publishing method not implemented.")

    def register_callback(self, cb_info):
        raise NotImplementedError("register_callback method not implemented.")
