
def f(): pass
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
class FunctionKey:
    def __hash__(self): return hash(f)
    def __eq__(self, other): return True
class Plain:
    pass
def constant():
    table = {Key(): 0}
    table.get(1)
def subscript():
    table = {Key(): 0}
    table[1]
def function():
    table = {FunctionKey(): 0}
    table.pop(f, None)
def same():
    key = Key()
    table = {key: 0}
    table.get(key)
def no_eq():
    table = {Plain(): 0, 1: 0}
    table.get(1)
constant()
subscript()
function()
same()
no_eq()
