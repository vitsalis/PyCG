
class Slots:
    def a(self): pass
    def b(self): pass
    def c(self): pass
    def d(self): pass
    def e(self): pass
def target(): pass
def run(obj):
    for name in Slots.__dict__:
        setattr(obj, name, target)
    obj.a()
run(Slots())
