from flask import render_template

from pyro_support import Pyro4Server, config

class BasicServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(self, name='BasicServer')

    @config.expose
    def square(self, x):
        if isinstance(x, str):
            x = float(x)
        return x**2

app, server = BasicServer.flaskify()

@app.route("/")
def main():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
