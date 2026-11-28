
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

class Hooked:
    hook = Hook()
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
class Child(Hooked):
    def run(self):
        super().hook
def use():
    Hooked().hook
