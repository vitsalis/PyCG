
import inspect
def action(): pass
def late(self): pass
class Base:
    def inherited(self): pass
def base():
    return Base
class Item(base()):
    def own(self): pass
    @property
    def computed(self):
        return action
def store(cls, obj):
    cls.late = late
    obj.callback = action
item = Item()
store(Item, item)
for name, member in inspect.getmembers(Item):
    member(item)
for name, member in inspect.getmembers(item):
    member()
for name, value in vars(Item).items():
    value(item)
for value in item.__dict__.values():
    value()
Item.__dict__["own"](item)
