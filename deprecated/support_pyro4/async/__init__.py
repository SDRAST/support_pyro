def async_method(func):
    def wrapper(self, *args, **kwargs):

        this.cb_info = cb_info
        this.socket_info = socket_info
        if not cb_info:
            this.cb = lambda *args, **kwargs: None
            this.cb_updates = lambda *args, **kwargs: None
            this.cb_handler = None
        else:
            cb = cb_info.get('cb', name+"_cb")
            this.cb_name = cb
            cb_updates = cb_info.get('cb_updates', name+"_cb_updates")
            this.cb_updates_name = cb_updates
            if not socket_info:
                cur_handler = getattr(self, "cb_handler", None)
                this.cb_handler = cb_info.get('cb_handler', cur_handler)
                try:
                    this.cb = getattr(this.cb_handler, cb)
                except AttributeError:
                    this.cb = lambda *args, **kwargs: None
                try:
                    this.cb_updates = getattr(this.cb_handler, cb_updates)
                except AttributeError:
                    this.cb_updates = lambda *args, **kwargs: None
            else:
                app = socket_info['app']
                socketio = socket_info['socketio']
                def f(cb_name):
                    def emit_f(*args, **kwargs):
                        with app.test_request_context("/"):
                            socketio.emit(cb_name, {"args": args, "kwargs":kwargs})
                    return emit_f

                this.cb_handler = None
                this.cb = f(cb)
                this.cb_updates = f(cb_updates)
