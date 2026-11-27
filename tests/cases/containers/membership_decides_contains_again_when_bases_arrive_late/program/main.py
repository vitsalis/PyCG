
class Needle:
    def __eq__(self, other): return True
class Bag:
    def __contains__(self, item): return False
class Items(list):
    def __init__(self):
        super().__init__([1])
class Holder:
    pass
class Names:
    second = "base"
holder = Holder()
holder.base = Bag
first = "second"
name = getattr(Names, first)
setattr(holder, name, Items)
class C(holder.base):
    pass
def use():
    Needle() in C()
class Box:
    run = use
key = "run"
getattr(Box, key)()
