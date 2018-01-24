import Pyro4

from support_pyro.support_pyro4.async import async

class Server(object):

    @async
    def square(self, x):
        self.square.cb(x**2)

    @async
    def repeat(self, word, times):
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
