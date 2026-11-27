
def f(): pass
def g(): pass
def h(): pass

import ext
def known():
    handler = f
    assert True, (handler := g)
    handler()
def unknown():
    handler = f
    assert ext.ok, (handler := g)
    handler()
