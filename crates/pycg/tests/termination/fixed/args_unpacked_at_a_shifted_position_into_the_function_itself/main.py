def g(): pass
def shift(*args):
    args[0]()
    shift(g, *args)
shift(g)
