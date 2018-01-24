## support_pyro
### Version 1.3.0a

Pyro4 server and client.

### Dependencies

- pyro4tunneling>=1.2.0
- Pyro4

### Usage

The recommended usage is to subclass `pyro_support.Pyro4Server`.

```python
# new_cool_server.py
import Pyro4

from pyro_support import Pyro4Server

class NewCoolServer(Pyro4Server):

    def __init__(self):
        Pyro4Server.__init__(name="NewCoolServer")

    @Pyro4.expose
    def new_cool_method(self):
        return "Wow, what a cool method!"


if __name__ == '__main__':
    s = NewCoolServer()
    s.launch_server()
```

Now to interface with this subclass, we do the following:

```python
# new_cool_client.py

import pyro4tunneling

t = pyro4tunneling(local=True)
p = t.get_remote_object("NewCoolServer")
print(p.new_cool_method())
```

Now, when I run `new_cool_client.py` I'll get the following output
(assuming that `new_cool_server.py` is running in the background):

```bash
me@local:/path/to/new_cool_client$ python new_cool_client.py
Wow, what a cool method!
me@local:/path/to/new_cool_client$
```

### Installation

Run `install.sh -i`. If you're running outside of a virtual environment,
the script will prompt you, asking if you want to continue. You'll also probably
have to use `sudo`.

To uninstall, run `install.sh -u`

### Testing

In the top level directory, type the following:

```bash
/path/to/pyro-support$ python -m unittest discover -s test -t .
```
