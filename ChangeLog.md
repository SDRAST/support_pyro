## ChangeLog for pyro-support

### Version 0.1

- Got rid of use of `logging_config` function from support.
- Got rid of unnecessary keyword arguments in `__init__`
- Renamed serverlog to logger. This is in keeping with recent changes to the
    rest of TAMS code.
- Moved Pyro4PublisherServer into its own repository.

### Version 1.0

- Got rid of dependence on `support`. I replaced with dependence on `pyro4tunneling`

### Version 1.1

- Added methods to automate creation of flask and flask_socketio methods.
- Added examples, including a basic web server/client pair.
- Attempted to add backward compatibility with older versions of Pyro4. This
will work with the server in Pyro mode. If one attempts to use an older version of
Pyro4 with the `flaskify` and `flaskify_io` methods, I don't know what will happen.
