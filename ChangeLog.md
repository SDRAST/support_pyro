## ChangeLog for pyro-support

### Version 1.0

- pyro4_server:
    - Got rid of use of `logging_config` function from support.
    - Got rid of unnecessary keyword arguments in `__init__`
    - Renamed serverlog to logger. This is in keeping with recent changes to the
        rest of TAMS code.
