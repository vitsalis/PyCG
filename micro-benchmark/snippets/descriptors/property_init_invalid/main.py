def read(self):
    return 1


class plain(property):
    pass


class Item:
    value = plain()


prop = Item.__dict__["value"]
for attempt in (
    lambda: property.__init__(prop, read, unexpected=1),
    lambda: property.__init__(self=prop, fget=read),
    lambda: property.__init__(prop, read, None, None, None, None),
):
    try:
        attempt()
    except TypeError:
        pass


def show(item):
    try:
        return item.value
    except AttributeError:
        return None


show(Item())
