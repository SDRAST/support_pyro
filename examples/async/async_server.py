import Pyro4

from support.pyro import async

class Server(object):

    @async.async_method
    def square(self, x):
        print("square: x: {}".format(x))
        self.square.cb(x**2)

    @async.async_method
    def repeat(self, word, times):
        print("repeat: word: {}, times: {}".format(word, times))
        word_list = [word for i in range(times)]
        res = " ".join(word_list)
        self.repeat.cb(res)

if __name__ == "__main__":
    port = 50001
    host = "localhost"
    with Pyro4.Daemon(port=port, host=host) as daemon:
        server = Server()
        uri = daemon.register(server, objectId="Server")
        print("Running daemon with uri {}".format(uri))
        daemon.requestLoop()
