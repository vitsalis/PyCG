
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

class Tool:
    def __call__(self): pass
class Box:
    tool = Tool()
def use():
    Box().tool()
