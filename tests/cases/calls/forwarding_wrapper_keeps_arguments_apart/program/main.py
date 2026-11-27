def f(): pass
def g(): pass
def h(): pass

def target(first, second, *, key=None):
    second()
    key()
def forward(*args, **kwargs):
    return target(*args, **kwargs)
forward(f, g, key=h)
