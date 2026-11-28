
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def use():
    for _, a in enumerate([f]):
        a()
    for _, b in zip(["s"], [g]):
        b()
    for c in reversed([h]):
        c()
    next(iter(enumerate([k])))[1]()
use()
