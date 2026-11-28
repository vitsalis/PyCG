
class C:
    key = (lambda: 1)
    def m(self):
        return (lambda: 2)()
f = lambda: 3
f()
C().m()
def target(): pass
pick = lambda: target
pick()()
