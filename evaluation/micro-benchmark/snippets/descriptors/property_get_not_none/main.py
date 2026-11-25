def read(obj):
    return obj


prop = property(read)


def with_false():
    return prop.__get__(False, int)


def with_float():
    return prop.__get__(1.5)


with_false()
with_float()
