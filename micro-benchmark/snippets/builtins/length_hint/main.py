class Sized:
    def __iter__(self):
        return iter([65])

    def __len__(self):
        return 1


class Hinted:
    def __iter__(self):
        return iter([65])

    def __length_hint__(self):
        return 1


def collect(*items):
    return items


def ordered(values):
    return sorted(values)


def displayed(values):
    return [*values], (*values,)


def unpacked(values):
    return collect(0, *values)


def converted(values):
    return bytes(values)


def extended(values):
    buffer = bytearray()
    buffer.extend(values)
    items = []
    items += values


for values in (Sized(), Hinted()):
    ordered(values)
    displayed(values)
    unpacked(values)
    converted(values)
    extended(values)
