HANDLERS = {}


def handles(event):
    def register(func):
        HANDLERS[event] = func
        return func

    return register


@handles("open")
def on_open():
    pass


@handles("close")
def on_close():
    pass


def dispatch(event):
    HANDLERS[event]()


dispatch("open")
