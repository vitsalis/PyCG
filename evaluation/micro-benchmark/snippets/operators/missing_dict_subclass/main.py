def make_default():
    return 0


class Defaults(dict):
    def __missing__(self, key):
        return make_default()


def lookup(table):
    return table["a"]


def safe_lookup(table):
    return table.get("b")


table = Defaults()
lookup(table)
safe_lookup(table)
