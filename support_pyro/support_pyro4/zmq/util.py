import threading

from .event_emitter import EventEmitter

class PausableThread(threading.Thread):
    """
    A simple thread extension that has pause, stop and unpause methods.
    """
    def __init__(self,*args,**kwargs):
        super(PausableThread, self).__init__(*args, **kwargs)
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.running_event = threading.Event()
        self.event_emitter = EventEmitter()

    def pause(self):
        self.pause_event.set()
        with self.lock:
            self.event_emitter.emit("pause")

    def unpause(self):
        self.pause_event.clear()
        with self.lock:
            self.event_emitter.emit("unpause")

    def stop(self):
        self.stop_event.set()
        with self.lock:
            self.event_emitter.emit("stop")

    def stopped(self):
        return self.stop_event.isSet()

    def paused(self):
        return self.pause_event.isSet()
