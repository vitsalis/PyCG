import functools


def read(self):
    return 1


class mixed(functools.cached_property, property):
    pass


class Item:
    value = mixed(read)


def show(item):
    return item.value


show(Item())
