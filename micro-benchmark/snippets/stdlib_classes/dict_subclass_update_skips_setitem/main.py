def record(key):
    pass


class Tracked(dict):
    def __setitem__(self, key, value):
        record(key)
        super().__setitem__(key, value)


def assign(table):
    table["a"] = 1


def bulk(table):
    table.update(b=2)


tracked = Tracked()
assign(tracked)
bulk(tracked)
