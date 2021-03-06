import logging
import threading
import time
import sys
import socket

import Pyro5
import six

__all__ = [
    "iterative_run",
    "Pause",
    "PausableThread",
    "PausableThreadCallback",
    "CoopPausableThread",
    "blocking",
    "non_blocking",
    "register_socket_error"
]

module_logger = logging.getLogger(__name__)


def iterative_run(run_fn):
    """
    A decorator for running functions repeatedly inside a PausableThread.
    Allows one to pause and stop the thread while its repeatedly calling
    the overridden run function.

    Args:
        run_fn (callable): the overridden run function from PausableThread
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

    This starts by pausing and input thread or threads and unpausing them when
    code inside block has been called.

    Attributes:
        thread (dict): A collection of threads to pause and unpause.
        init_pause_status (dict): The initial state of the threads in
            the thread attribute.
	  """
    def __init__(self, pausable_thread):
        """
		    If we pass "None", then this gets dealt with properly down stream.
		    
		    @param pausable_thread : instance or list of PausableThread objects
		    @type  pausible_thread : list, PausableThread
		    """
        self.thread = pausable_thread
        if not isinstance(self.thread, dict):
            # if the argument is not a dict, make it one
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
        Pause the thread in question, and make sure that whatever
        functionality is being performing is actually stopped.
        """
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                # if there really is a thread
                if not self.init_pause_status[name]:
                    # and it is not already paused
                    t.pause_thread()
            else:
                pass
        # now make sure that they're actually paused.
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                # if there really is a thread
                while self.thread[name].running():
                    # wait until it is no longer running
                    time.sleep(0.001)
            else:
                pass

    def __exit__(self, *args):
        """
        Unpause the thread
        """
        for name in self.thread.keys():
            t = self.thread[name]
            if t:
                # if there really is a thread
                if not self.init_pause_status[name]:
                    self.thread[name].unpause_thread()
            else:
                pass


class PausableThread(threading.Thread):
    """
    A pausable, stoppable thread.
    
	It also has a running flag that can be used to determine if the process is
	still running. This is meant to be subclassed.

    Attributes:
        name (str): name of thread, if any
        daemon (bool): Daemon status
        logger (logging.getLogger): logging instance.
        _lock (threading.Lock): thread's internal lock
        _pause_event (threading.Event): setting and clearing this indicates to
            pause or unpause thread.
        _stop_event (threading.Event): setting this stops thread.
        _running_event (threading.Event): setting this indicates thread is
            currently executing "run" method.
	  """
    def __init__(self, *args, **kwargs):
        """
        create a pausable thread
        
        Args:
            args: passed to super class
            kwargs: passed to super class
		    """
		    # get the name of the thread from kwargs or set to default
		    # remove from kwargs
        name = kwargs.pop("name","PausableThread")
        logger = kwargs.pop("logger",None)
        super(PausableThread, self).__init__(*args, **kwargs)
        if logger is None:
            self.logger = module_logger.getChild(name)
        self.logger = logger
        self.name = name
        self.daemon = True
        self._lock = threading.Lock()
        # create events for the thread states
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._running_event = threading.Event()

    def stop_thread(self):
        """
        Set self._stop_event

		    Stop the thread from running all together. Make
		    sure to join this up with threading.Thread.join()
        For compatibility
        """
        self._stop_event.set()

    def stop(self):
        """Alias for self.stop_thread"""
        return self.stop_thread()

    def pause_thread(self):
        """Set self._pause_event"""
        self._pause_event.set()

    def pause(self):
        """Alias for self.pause_thread"""
        return self.pause_thread()

    def unpause_thread(self):
        """Clear self._pause_event"""
        self._pause_event.clear()

    def unpause(self):
        """Alias for self.unpause_thread"""
        return self.unpause_thread()

    def stopped(self):
        return self._stop_event.isSet()

    def paused(self):
        return self._pause_event.isSet()

    def running(self):
        return self._running_event.isSet()


class PausableThreadCallback(PausableThread):
    """
    A thread that runs the same callback over an over again.
    This thread can be paused, unpaused, and stopped in a thread-safe manner.
    """
    def __init__(self, *args, **kwargs):
        super(PausableThreadCallback, self).__init__(*args, **kwargs)
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


class CoopPausableThread(PausableThreadCallback):

    def run(self):
        self._running_event.set()
        for e in self.callback(*self.callback_args, **self.callback_kwargs):
            if self.stopped():
                break
        self._running_event.clear()


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

