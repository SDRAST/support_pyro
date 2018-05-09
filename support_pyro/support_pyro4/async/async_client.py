import logging
import contextlib
import inspect
import time

import Pyro4

__all__ = ["AsyncClient"]

module_logger = logging.getLogger(__name__)

class AsyncClient(object):
    """
    Class that stores information about methods with the async.async_callback
    decorator.
    This class is meant to be subclassed, not used on its own.

    Examples:

    .. code-block:: python

        from support.pyro import async

        class MyAsyncClient(async.AsyncClient):

            def __init__(self, **kwargs):
                super(MyAsyncClient, self).__init__(**kwargs)

            @async.async_callback
            def async_method(self):
                self.async_method.cb()

            def sync_method(self);
                pass

    """
    def __init__(self, uri_or_proxy=None, proxy_class=None):
        self._async_methods = self._get_async_methods()
        self._called = {name[0]:False for name in self._async_methods}
        self._calls = {name[0]:0 for name in self._async_methods}
        self._res = {name[0]:None for name in self._async_methods}
        if proxy_class is None:
            from .async_proxy import AsyncProxy
            proxy_class = AsyncProxy

        proxy = None
        if uri_or_proxy is not None:
            if isinstance(uri_or_proxy, Pyro4.core.URI) or hasattr(uri_or_proxy, "format"):
                proxy = proxy_class(uri_or_proxy)
            else:
                proxy = uri_or_proxy
        self.proxy = proxy

    def __getattr__(self, attr):
        if self.proxy is not None:
            return getattr(self.proxy, attr)
        else:
            super(AsyncClient, self).__getattr__(attr)

    def _get_async_methods(self):
        """
        Get all methods in this class or subclass that have
        @async.async_callback decorator.

        Returns:
            list: Each element is a tuple with the following signature:
                (method_name, method), where ``method_name`` is the name of the
                method, and ``method`` is the method object.
        """
        async_methods = []
        for method_pair in inspect.getmembers(self):
            method_name, method = method_pair
            if hasattr(method, "_asyncCallback"):
                if method._asyncCallback:
                    async_methods.append(method_pair)
        return async_methods

    @contextlib.contextmanager
    def wait(self, method_names, timeout=None):
        """
        Context manager to wait for callbacks to be called.

        Examples:

        .. code-block:: python

            class Client(async.AsyncClient):

                @async.async_callback
                def handler(self,res):
                    print(res)

            client = Client()

            uri = "PYRO:<objectId>@<host>:<port>"
            proxy = async.AsyncProxy(uri)
            with client.wait(client.handler):
                proxy.some_method(callback=client.handler)
            # OR
            with client.wait("handler"):
                proxy.some_method(callback=client.handler)


        Args:
            method_names (list): List of methods to wait for.
                Can be list of string method names, or list of methods themselves
            timeout (float, optional): Break after this amount of time,
                regardless if methods have been called.

        """
        if hasattr(method_names, "format") or inspect.ismethod(method_names):
            method_names = [method_names]

        async_method_names = [m[0] for m in self._async_methods]
        async_methods = [m[1] for m in self._async_methods]

        for i in xrange(len(method_names)):
            method_or_name = method_names[i]
            if (method_or_name not in async_method_names and
                method_or_name not in async_methods):
                raise RuntimeError("wait: {} not in this class's async methods {}".format(method_name, async_method_names))
            if inspect.ismethod(method_or_name):
                method_names[i] = method_or_name.__name__

        current_calls = [self._calls[method_name] for method_name in method_names]

        yield

        t0 = time.time()
        while any([self._calls[method_names[i]] == current_calls[i] for i in xrange(len(method_names))]):
            if timeout is None:
                pass
            else:
                if (time.time() - t0) >= timeout:
                    break
