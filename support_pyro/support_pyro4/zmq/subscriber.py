import Pyro4

from ..async.async_proxy import AsyncProxy

class Subscriber(object):

    def __init__(self, uri):
        self.proxy = AsyncProxy(uri)
        self._serializer_name = self.proxy.serializer_name
        self._serializer = self.proxy.serializer

    def __getattr__(self, attr):
        return getattr(self.proxy, attr)

    def start_subscribing(self):
        pass

    def pause_subscribing(self):
        pass

    def unpause_subscribing(self):
        pass

    def stop_subscribing(self):
        pass

    def _consume_msg(self, msg):
        """Deserialize the message from server"""
        res = self._serializer.loads(msg)
        self.consume(res)
        return res

    def consume(self, res):
        """Meant to be reimplemented in child subclass"""
        raise NotImplementedError
