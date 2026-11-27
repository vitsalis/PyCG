
def helper(callback):
    callback()
def g(): pass
class C:
    run = staticmethod(helper)
C().run(g)
