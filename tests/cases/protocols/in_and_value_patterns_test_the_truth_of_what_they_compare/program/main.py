
class Truth:
    def __bool__(self): return True
class Box:
    def __contains__(self, item): return Truth()
class Value:
    def __eq__(self, other): return Truth()
class Holder:
    value = Value()
def contains(box):
    1 not in box
def pattern(value):
    match value:
        case Holder.value:
            pass
contains(Box())
pattern(Value())
