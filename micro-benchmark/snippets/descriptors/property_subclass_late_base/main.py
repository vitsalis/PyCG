def choose():
    return property


def read(self):
    return 1


class tracked(choose()):
    pass


class Item:
    value = tracked(read)


def show(item):
    return item.value


show(Item())
