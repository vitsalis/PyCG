
def a(): pass
def b(): pass
def choose(f):
    class C:
        f = None
        def reset(self):
            nonlocal f
            f = b
    C().reset()
    return f
choose(a)()
