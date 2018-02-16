import logging
import threading
import time
import sys

import Pyro4
import six

__all__ = ["iterative_run", "Pause",
           "PausableThread", "PausableThreadCallback",
           "blocking", "non_blocking",
           "EventEmitter"]

module_logger = logging.getLogger(__name__)

def iterative_run(run_fn):
    """
    A decorator for running functions repeatedly inside a PausableThread.
    Allows one to pause and stop the thread while its repeatedly calling
    the overridden run function.
    Args:
        run_fn: the overridden run function from PausableThread
    Returns:
        callable: wrapped function
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
    def __init__(self, *args, **kwargs):
        """
		"""
        name = kwargs.pop("name","PausableThread")
        logger = kwargs.pop("logger",None)
        super(PausableThread, self).__init__(*args, **kwargs)
        if logger is None:
            self.logger = logging.getLogger("{}.{}".format(module_logger.name, name))
        else:
            self.logger = logger
        self.name = name
        self.daemon = True
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._running_event = threading.Event()

    def stop_thread(self):
        """
		Stop the thread from running all together. Make
		sure to join this up with threading.Thread.join()
        For compatibility
		"""
        self._stop_event.set()

    def stop(self):
        return self.stop_thread()

    def pause_thread(self):
        """For compatibility"""
        self._pause_event.set()

    def pause(self):
        return self.pause_thread()

    def unpause_thread(self):
        """For compatibility"""
        self._pause_event.clear()

    def unpause(self):
        return self.unpause_thread()

    def stopped(self):
        return self._stop_event.isSet()

    def paused(self):
        return self._pause_event.isSet()

    def running(self):
        return self._running_event.isSet()

class PausableThreadCallback(PausableThread):
    """
	A thread that runs the same callback over an over again, with some
	predetermined wait time.
	This thread can be paused, unpaused, and stopped in a thread-safe manner.
	"""

    def __init__(self, *args, **kwargs):
        super(PausableThreadCallback, self).__init__(self, *args, **kwargs)
        if sys.version_info[0] == 2:
            self.callback = self._Thread__target
            self.callback_args = self._Thread__args
            self.callback_kwargs = self._Thread__kwargs
        else:
            self.callback = self._target
            self.callback_args = self._args
            self.callback_kwargs = self._kwargs

    def run(self):

        while True:
            if self.stopped():
                break

            if self.paused():
                time.sleep(0.001)
                continue
            else:
                self._running.set()
                self.callback(*self.callback_args, **self.callback_kwargs)
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

class EventEmitter(object):

    def __init__(self, threaded=True):
        self.threaded = threaded
        self._lock = threading.Lock()
        self.__handlers = {}

    def emit(self, event_name, *args, **kwargs):
        def emitter():
            if event_name in self.__handlers:
                for handler in self.__handlers[event_name]:
                    with self._lock:
                        module_logger.debug(
                            "Emitting handler {} for event {}".format(handler,event_name)
                        )
                        handler(*args, **kwargs)

        if self.threaded:
            t = threading.Thread(target=emitter)
            t.daemon = True
            t.start()
        else:
            emitter()

    def on(self, event_name, callback):
        with self._lock:
            if event_name not in self.__handlers:
                self.__handlers[event_name] = []
            self.__handlers[event_name].append(callback)
