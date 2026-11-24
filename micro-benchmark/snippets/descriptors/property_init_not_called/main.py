def read(self):
    return 1


class keeps(property):
    def __init__(self, fget):
        self.kept = fget


class Item:
    value = keeps(read)


def show(item):
    try:
        return item.value
    except AttributeError:
        return None


show(Item())
