def read(self):
    return 1


class plain(property):
    pass


class Item:
    pass


def show(item):
    return item.value


item = Item()
item.value = plain(read)
show(item)
