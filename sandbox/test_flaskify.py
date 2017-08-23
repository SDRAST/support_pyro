from pyro_support import Pyro4Server

server = Pyro4Server(name="TestFlaskifyServer", simulated=True)
app, _ = Pyro4Server.flaskify(server)
# app, server = Pyro4Server.flaskify(name="TestFlaskifyServer",
#                                    simulated=True)
app.run(debug=True)
