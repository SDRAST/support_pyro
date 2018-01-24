import functools

import Pyro4

def async(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        callback = kwargs.pop("callback",None)
        if callback is None:
            wrapper.callback = lambda *args, **kwargs: None
        elif callable(callback):
            wrapper.callback = callback
        else:
            handler = callback["handler"]
            callback_name = callback["callback"]
            wrapper.callback = getattr(handler, callback_name)
        return fn(self, *args, **kwargs)

    wrapper._pyroAsync = True
    return Pyro4.expose(Pyro4.oneway(wrapper))
