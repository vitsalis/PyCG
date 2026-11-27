class Handler:
    def on_open(self):
        pass

    def on_close(self):
        pass

def dispatch(handler, event):
    getattr(handler, "on_" + event)()

dispatch(Handler(), "close")
