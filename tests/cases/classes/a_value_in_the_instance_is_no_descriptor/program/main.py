
def f(): pass
class Hook:
    def __get__(self, obj, owner=None):
        owner.made()
        obj.used()
        return f
class App:
    hook = Hook()
    @classmethod
    def made(cls): pass
    def used(self): pass

class Bare:
    pass
def use():
    bare = Bare()
    bare.hook = Hook()
    bare.hook
