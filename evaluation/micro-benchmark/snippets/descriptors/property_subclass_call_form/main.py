class logged(property):
    pass


def get_size(self):
    return 1


def set_size(self, value):
    pass


class Box:
    size = logged(get_size, set_size)


def resize(box):
    box.size = 2


def measure(box):
    return box.size


box = Box()
resize(box)
measure(box)
