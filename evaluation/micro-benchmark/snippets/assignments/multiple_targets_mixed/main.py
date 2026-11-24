def func1():
    pass

class Box:
    pass

box = Box()
table = {}
box.handler = table["handler"] = func1
box.handler()
table["handler"]()
