
@async_method
def start_publishing(self, host="localhost", port=0, threaded=True):
    """
    Start publishing. This can either be called server side or client side.
    Keyword Args:
    """
    # class ContextualizedPublisher(EventEmitter):
    #
    #     def __init__(self, context, callback, serializer, host="localhost", port=0):
    #         EventEmitter.__init__(self, threaded=False)
    #         self.context = context
    #         self.callback = callback
    #         self.serializer = serializer
    #         if host == "localhost":
    #             host = "*"
    #         self.host = host
    #         if port == 0:
    #             port = Pyro4.socketutil.findProbablyUnusedPort()
    #         self.port = port
    #         self.address = "tcp://{}:{}".format(self.host, self.port)
    #         self.socket = None
    #         self.started = False
    #
    #     def __call__(self):
    #         if not self.started:
    #             self.socket = SocketSafetyWrapper(self.context.socket(zmq.PUB))
    #             print("__call__: {}".format(threading.current_thread()))
    #             self.socket.bind(self.address)
    #             self.started = True
    #         else:
    #             res = self.callback()
    #             print("__call__: {}".format(threading.current_thread()))
    #             self.socket.send(self.serializer.dumps(res))
    #
    #     def close_socket(self):
    #         if self.socket is not None:
    #             self.socket.close`(`)
    # def publisher():
    #     results = self.publish()
    #     socket.send(self._serializer.dumps(results))
    # if host == "localhost":
    #     host = "*"
    # socket.bind("tcp://{}:{}".format(host, port))
    # self._socket = socket

    # publisher = ContextualizedPublisher(self._context,
    #                                     self.publish,
    #                                     self._serializer)
    # # publisher.on("close", publisher.close_socket)
    # self._contextualized_publisher = publisher
