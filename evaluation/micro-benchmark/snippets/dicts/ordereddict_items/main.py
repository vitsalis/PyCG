from collections import OrderedDict


def func1():
    pass


def func2():
    pass


handlers = OrderedDict()
handlers["first"] = func1
handlers.setdefault("second", func2)
for name, handler in handlers.items():
    handler()
