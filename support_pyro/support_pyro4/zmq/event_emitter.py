import threading

class EventEmitter(object):

    def __init__(self):

        self.__handlers = {}

    def emit(self, event_name, *args, **kwargs):
        def emitter():
            if event_name in self.__handlers:
                for handler in self.__handlers[event_name]:
                    handler(*args, **kwargs)

        t = threading.Thread(target=emitter)
        t.daemon = True
        t.start()

    def on(self, event_name, callback):
        if event_name not in self.__handlers:
            self.__handlers[event_name] = []
        self.__handlers[event_name].append(callback)
