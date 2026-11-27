
def target(): pass
def put(self, name, value):
    value()
class C: pass
name = f"__setattr__"
setattr(C, name, put)
C().anything = target
