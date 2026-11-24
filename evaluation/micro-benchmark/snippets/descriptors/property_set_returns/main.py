def other():
    pass


class plain(property):
    pass


def put(self, value):
    return other


class Box:
    size = plain(None, put)


box = Box()
result = Box.__dict__["size"].__set__(box, 1)
if callable(result):
    result()
