
def f(): pass
def g(): pass
def h(): pass

def run():
    flag = False
    try:
        raise ExceptionGroup("errors", [ValueError(), TypeError()])
    except* ValueError:
        flag = True
        raise RuntimeError()
    except* TypeError:
        if flag:
            f()
