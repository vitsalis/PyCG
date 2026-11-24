def put(self, value):
    pass


def drop(self):
    pass


class frozen(property):
    def __set__(self, instance, value):
        pass

    def __delete__(self, instance):
        pass


class Item:
    value = frozen(None, put, drop)


def change(item):
    item.value = 1


def remove(item):
    del item.value


item = Item()
change(item)
remove(item)
