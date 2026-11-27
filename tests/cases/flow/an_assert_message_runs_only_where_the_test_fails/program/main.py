
def f(): pass
def g(): pass
def h(): pass

import ext
def holds():
    assert True, f()
    g()
def unknown():
    assert ext.check(), f()
    g()
def fails():
    assert (), f()
    g()
