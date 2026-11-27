
def keep(f):
    def reset():
        nonlocal f
        f = None
    return f
@keep
def first(): pass
@keep
def second(): pass
def use():
    first()
