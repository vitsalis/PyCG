
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

class Field:
    def __set__(self, obj, value):
        value()
    def __delete__(self, obj):
        obj.used()
class User:
    email = Field()
    def used(self): pass
def use():
    user = User()
    user.email = f
    del user.email
