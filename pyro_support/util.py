import logging
import threading
import time

import six

module_logger = logging.getLogger(__name__)

class AsyncCallback(object):
    """
    Creates an object that has two callable attributes:
    cb: A 'final' callback function -- a client side method that is meant
        to be called when a server side method is finished
    cb_updates: An 'update' callback function -- a client side method that is
        meant to be called when the server side method has new information for
        the client
    """
    def __init__(self, cb_info=None, socket_info=None, func_name=None):
        """
        Keyword Args:
            cb_info (dict): Callback info (None)
            socket_info (dict): Information about the flask_socketio socket (None)
        """
        # print("AsyncCallback: cb_info: {}".format(cb_info))
        if not cb_info:
            self.cb = lambda *args, **kwargs: None
            self.cb_updates = lambda *args, **kwargs: None
            self.cb_handler = None
        else:
            dummy = lambda *args, **kwargs: None
            self.cb_handler = cb_info.get('cb_handler', None)
            for key in ["cb", "cb_updates"]:
                cb = cb_info.get(key, None)
                if not cb:
                    setattr(self, key, dummy)
                if callable(cb):
                    setattr(self, key, cb)
                elif isinstance(cb, six.string_types):
                    if socket_info:
                        app = socket_info['app']
                        socketio = socket_info['socketio']
                        def f(cb_name):
                            def emit_f(*args, **kwargs):
                                with app.test_request_context("/"):
                                    socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
                            return emit_f
                        setattr(self, key, f(cb))
                    else:
                        if self.cb_handler:
                            try:
                                setattr(self, key, getattr(self.cb_handler, cb))
                                setattr(self, key+"_name", cb)
                            except AttributeError as err:
                                setattr(self, key, dummy)
                        else:
                            raise RuntimeError("Need to provide a callback handler of type Pyro4.core.Proxy")
        # print("AsyncCallback: self.cb: {}".format(self.cb))

def async_method(func):
    """
    Decorator that declares that a method is to be called asynchronously.
    Methods that are decorated with this class use a common callback interface.
    Say you have a server side method, `long_running_method` decorated with
    `async_method`:

    ```python
    ...
    @async_method
    def long_running_method(self, *args, **kwargs):
        ...
        self.long_running_method.cb_updates(update_info)
        ...
        self.long_running_method.cb(final_info)
    ...
    ```

    Any method that is decorated with this decorator will have three new attributes:
    "cb", "cb_updates", and "cb_handler". This assumes no a priori information about
    the client to which we are connected.

    Now client side, we would call `long_running_method` as follows:

    ```python
    # Here handler is some Pyro4.Daemon that has some methods/objects registered to it.
    client.long_running_method(*args,cb_info={'cb_handler':handler,
                                        "cb":"long_running_method_cb",
                                        "cb_updates":"long_running_method_cb_updates"})
    ```

    This is no doubt a little verbose client side, but it helps to create a clear
    and consistent separation between client and server.

    Note that you can also decorate "__init__" functions, but the behavior is different.
    Instead of setting *function* attributes, we set *instance attributes*. This is mostly
    useful for worker threads:

    ```python
    class Worker(threading.Thread):

        @async_method
        def __init__(self,*args, **kwargs):
            threading.Thread.__init__(self)

        def run(self):
            ...
            self.cb_updates(update_info)
            ...
            self.cb(cb_info)
    ```

    I wouldn't recommend using this on large classes, because it clutters and confuses
    the attribute space.

    Args:
        func (function): Function or method we'd like to decorate
    """
    def wrapper(self, *args, **kwargs):
        """
        Process cb_info dictionary, setting function attributes accordingly.
        The decorator assumes a cb_info dictionary with the following keys:
        cb_info:
            cb_handler (Pyro4.Daemon): The handler object
            cb (str): The name of the final callback
            cb_updates (str, optional): The name of the updates callback
        """
        name = func.__name__
        if name == "__init__": # We're decorating a class, namely a worker class
            this = self
        else:
            this = wrapper
        module_logger.debug("{}: {}".format(name, kwargs))
        if 'cb_info' in kwargs:
            cb_info = kwargs['cb_info']
            kwargs.pop('cb_info')
        else:
            cb_info = None

        if 'socket_info' in kwargs:
            socket_info = kwargs['socket_info']
            kwargs.pop('socket_info')
        else:
            socket_info = None

        this.cb_info = cb_info
        this.socket_info = socket_info
        module_logger.debug("{}: {}".format(name, this.cb_info))
        module_logger.debug("{}: {}".format(name, this.socket_info))
        cur_handler = getattr(self, "cb_handler", None)
        if this.cb_info:
            if "cb_handler" not in this.cb_info:
                this.cb_info["cb_handler"] = cur_handler
        async_cb = AsyncCallback(cb_info=this.cb_info, socket_info=this.socket_info, func_name=name)
        this.cb = async_cb.cb
        this.cb_updates = async_cb.cb_updates
        this.cb_handler = async_cb.cb_handler
        try:
            this.cb_name = async_cb.cb_name
            this.cb_updates_name = async_cb.cb_updates_name
        except AttributeError:
            pass

        # this.cb_info = cb_info
        # this.socket_info = socket_info
        # if not cb_info:
        #     this.cb = lambda *args, **kwargs: None
        #     this.cb_updates = lambda *args, **kwargs: None
        #     this.cb_handler = None
        # else:
        #     cb = cb_info.get('cb', name+"_cb")
        #     this.cb_name = cb
        #     cb_updates = cb_info.get('cb_updates', name+"_cb_updates")
        #     this.cb_updates_name = cb_updates
        #     if not socket_info:
        #         cur_handler = getattr(self, "cb_handler", None)
        #         this.cb_handler = cb_info.get('cb_handler', cur_handler)
        #         try:
        #             this.cb = getattr(this.cb_handler, cb)
        #         except AttributeError:
        #             this.cb = lambda *args, **kwargs: None
        #         try:
        #             this.cb_updates = getattr(this.cb_handler, cb_updates)
        #         except AttributeError:
        #             this.cb_updates = lambda *args, **kwargs: None
        #     else:
        #         app = socket_info['app']
        #         socketio = socket_info['socketio']
        #         def f(cb_name):
        #             def emit_f(*args, **kwargs):
        #                 with app.test_request_context("/"):
        #                     socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
        #             return emit_f
        #
        #         this.cb_handler = None
        #         this.cb = f(cb)
        #         this.cb_updates = f(cb_updates)

        return func(self, *args, **kwargs)
    wrapper._async_method = True
    return wrapper


def iterative_run(run_fn):
    """
    A decorator for running functions repeatedly inside a PausableThread.
    Allows one to pause and stop the thread while its repeatedly calling
    the overriden run function.
    Args:
        run_fn: the overridden run function from PausableThread

    Returns:

    """
    def wrapper(self):

        while True:
            if self.stopped():
                break
            if self.paused():
                time.sleep(0.001)
                continue
            else:
                self._running_event.set()
                run_fn(self)
                self._running_event.clear()

    return wrapper


class Pause(object):
    """
	A context manager for pausing threads.
	This makes sure that when we unpause the thread when we're done
	doing whatever task we needed.
	"""

    def __init__(self, pausable_thread):
        """
		args:
		    - pausable_thread (list, PausableThread): An instance, or
			    list of instances of PausableThread.
			    If we pass "None", then this gets dealt with properly down stream.
		"""
        self.thread = pausable_thread
        if not isinstance(self.thread, dict):
            self.thread = {'thread': self.thread}

        self.init_pause_status = {}
        for name in self.thread.keys():
            if self.thread[name]:
                self.init_pause_status[name] = self.thread[name].paused()
            else:
                self.init_pause_status[name] = None
        # self.init_pause_status = {name: self.thread[name].paused() for name in self.thread.keys()}

    def __enter__(self):
        """
		Pause the thread in quesiton, and make sure that whatever
		functionality is being performing is actually stopped.
		"""
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                if not self.init_pause_status[name]:
                    t.pause_thread()
            else:
                pass
        # now make sure that they're actually paused.
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                while self.thread[name].running():
                    time.sleep(0.001)
            else:
                pass

    def __exit__(self, *args):
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                if not self.init_pause_status[name]:
                    self.thread[name].unpause_thread()
            else:
                pass

class PausableThread(threading.Thread):
    """
    A pausable, stoppable thread.
	It also has a running flag that can be used to determine if the process is still running.
	"""
    def __init__(self, name="PausableThread", logger=None):
        """
		"""
        threading.Thread.__init__(self)
        self.daemon = True
        self.name = name
        if not logger:
            self.logger = logging.getLogger("{}.{}".format(module_logger.name, name))
        else:
            self.logger = logger
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._running_event = threading.Event()

    def stop_thread(self):
        """
		Stop the thread from running all together. Make
		sure to join this up with threading.Thread.join()
		"""
        self._stop_event.set()

    def pause_thread(self):
        self._pause_event.set()

    def unpause_thread(self):
        self._pause_event.clear()

    def stopped(self):
        return self._stop_event.isSet()

    def paused(self):
        return self._pause_event.isSet()

    def running(self):
        return self._running_event.isSet()

class PausableThreadCallback(threading.Thread):
    """
	A thread that runs the same callback over an over again, with some
	predetermined wait time.
	This thread can be paused, unpaused, and stopped in a thread-safe manner.
	"""

    def __init__(self, callback, name=None, *args):

        threading.Thread.__init__(self)

        self.name = name
        self.callback = callback
        self.args = args

        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._running_event = threading.Event()

    def run(self):

        while True:
            if self.stopped():
                break

            if self.paused():
                time.sleep(0.001)
                continue
            else:
                self._running.set()
                self.callback(*self.args)
                self._running.clear()

    def stop_thread(self):

        self._stop_event.set()

    def pause_thread(self):

        self._pause_event.set()

    def unpause_thread(self):

        self._pause_event.clear()

    def stopped(self):

        return self._stop_event.isSet()

    def paused(self):

        return self._pause_event.isSet()

    def running(self):

        return self._running_event.isSet()

def blocking(func):
    """
    This decorator will make it such that the server can do
    nothing else while func is being called.
    """
    def wrapper(self, *args, **kwargs):
        lock = self.lock
        with lock:
            res = func(self, *args, **kwargs)
        return res
    return wrapper


def non_blocking(func):
    """
    Proceed as normal unless a functuon with the blocking
    decorator has already been called
    """
    def wrapper(self, *args, **kwargs):
        lock = self.lock
        while lock.locked():
            time.sleep(0.01)
        time.sleep(0.01)
        res = func(self, *args, **kwargs)
        return res

    return wrapper

if __name__ == '__main__':
    def callback():
        print("Called!")
        time.sleep(5.0)


    t = PausableThreadCallback(callback, name='test')
    t.daemon = True
    # t.pause()
    # t.start()
    # t.unpause()
    # print("Starting thread.")
    # t.start()
    # time.sleep(0.1)
    # print("Pausing thread.")
    # t.pause()
    # for i in xrange(7):
    # 	print("Is the callback still running? {}".format(t.running()))
    # 	time.sleep(1.0)
    # print("Unpausing thread.")
    # t.unpause()
    # time.sleep(5.0)
    # print("Stopping thread.")
    # t.stop()
    # t.join()
