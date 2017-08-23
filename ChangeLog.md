## ChangeLog for pyro-support

### pyro4_server
#### Version 0.1

- Got rid of use of `logging_config` function from support.
- Got rid of unnecessary keyword arguments in `__init__`
- Renamed serverlog to logger. This is in keeping with recent changes to the
    rest of TAMS code.
- Moved Pyro4PublisherServer into its own repository.

#### Version 1.0

- Got rid of dependence on `support`. I replaced with dependence on `pyro4tunneling`
