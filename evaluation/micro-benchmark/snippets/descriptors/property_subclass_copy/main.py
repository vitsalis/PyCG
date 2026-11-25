class plain(property):
    pass


def first(self):
    return 1


def second(self):
    return 2


class Item:
    a = plain(first)
    b = a.getter(second)


def use_a(item):
    return item.a


def use_b(item):
    return item.b


item = Item()
use_a(item)
use_b(item)
