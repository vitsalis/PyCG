def read(self):
    return 1


class forwarding(property):
    def __get__(self, instance, owner=None):
        return super().__get__(instance, owner)


class Item:
    value = forwarding(read)


def through_class():
    return Item.value


through_class()
