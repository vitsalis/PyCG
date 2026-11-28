
class Handler:
    def on_handler(self): pass
def dispatch(handler):
    getattr(handler, "on{²}_handler".format(**{"²": "x"}))
    getattr(handler, "on_{0}".format("x"))()
dispatch(Handler())
