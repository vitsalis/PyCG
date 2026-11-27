import broken, nul, chain


def deco(f):
    return f


@deco
def show(items, key):
    for item in items:
        match item:
            case {"name": name}:
                print(f"{name!r:>8}")
    return sorted(items, key=lambda item: item[key])
