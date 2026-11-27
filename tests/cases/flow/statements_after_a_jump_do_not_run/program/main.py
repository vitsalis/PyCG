
def f(): pass
def g(): pass
def h(): pass

import ext
def returned():
    f()
    return
    g()
def raised():
    raise ValueError()
    g()
def every_branch():
    if ext.flag:
        return f()
    else:
        raise ValueError()
    g()
def looped():
    for item in ext.items:
        if ext.flag:
            continue
            g()
        break
        h()
    f()
def finished():
    try:
        return f()
    finally:
        ext.release()
    g()
