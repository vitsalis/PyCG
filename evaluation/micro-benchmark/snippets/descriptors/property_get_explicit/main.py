def read(self):
    return 1


class quiet(property):
    def __get__(self, instance, owner=None):
        return 0


class Item:
    value = quiet(read)


def peek(item):
    return property.__get__(Item.__dict__["value"], item)


peek(Item())
