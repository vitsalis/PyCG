
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

def load():
    App.hook()
