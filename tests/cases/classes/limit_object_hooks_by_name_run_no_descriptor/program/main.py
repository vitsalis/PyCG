
class Field:
    def __get__(self, obj, owner=None): pass
    def __set__(self, obj, value): pass
    def __delete__(self, obj): pass
class User:
    email = Field()
    def by_object(self):
        object.__setattr__(self, "email", 1)
        object.__getattribute__(self, "email")
        object.__delattr__(self, "email")
    def by_super(self):
        super().__setattr__("email", 1)
        super().__delattr__("email")
User().by_object()
User().by_super()
