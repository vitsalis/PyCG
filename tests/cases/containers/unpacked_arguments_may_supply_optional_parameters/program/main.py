
class C:
    def m(self): pass
def target(): pass
xs = [C()]
list(*(xs,))[0].m()
for _ in iter(*(target, None)):
    pass
