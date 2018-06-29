from support.pyro import async, Pyro4Server

class BasicServer(Pyro4Server):

    def __init__(self):
        super(BasicServer, self).__init__(obj=self)

    @async.async_method
    def square(self, x):
        print("square: x: {}".format(x))
        res = x**2
        self.square.cb(res)
        return res

    @async.async_method
    def repeat(self, word, times, delimiter=", "):
        print("repeat: word: {}, times: {}".format(word, times))
        res = delimiter.join([word for i in range(times)])
        self.repeat.cb(res)
        return res

if __name__ == "__main__":
    server = BasicServer()
    server.launch_server(ns=False,objectId="BasicServer",objectPort=9091)
