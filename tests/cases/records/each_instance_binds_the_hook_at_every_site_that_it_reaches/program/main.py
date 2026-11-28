
class Logged:
    def __setattr__(self, name, value): pass
    def __delattr__(self, name): pass
class Keeper:
    def put(self, name, value): pass
class Kept:
    pass
def paint(shape):
    shape.color = 1
    shape.width = 2
def erase(shape):
    del shape.color
first = Logged()
second = Logged()
paint(first); paint(second); erase(first)
keeper = Keeper()
Kept.__setattr__ = keeper.put
paint(Kept()); paint(Kept())
