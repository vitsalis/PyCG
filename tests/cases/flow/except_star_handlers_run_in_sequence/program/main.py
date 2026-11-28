
def f(): pass
def g(): pass
def h(): pass

def run():
    handler = f
    try:
        raise ExceptionGroup("errors", [ValueError(), TypeError()])
    except* ValueError:
        handler = g
    except* TypeError:
        handler()
