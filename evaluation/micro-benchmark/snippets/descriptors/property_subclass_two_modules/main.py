from props import tracked


def read(self):
    return 1


class Item:
    value = tracked(read)


def show(item):
    return item.value


show(Item())
