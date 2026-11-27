
class C:
    def a(): pass
    def other(): pass
    b = c = d = e = other
name = "a"
def first(value):
    global name
    name = value
def second(value):
    global name
    name = value
def third(value):
    global name
    name = value
for setter in (first, second, third):
    setter("b")
    setter("c")
    setter("d")
    setter("e")
getattr(C, name)()
