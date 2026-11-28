
def f(): pass
def g(): pass
def h(): pass

import ext
def handled():
    try:
        return ext.run()
    except ValueError:
        pass
    f()
def managed():
    with ext.manager():
        return ext.run()
    g()
