from collections import UserDict


def record(key):
    pass


class Tracked(UserDict):
    def __setitem__(self, key, value):
        record(key)
        super().__setitem__(key, value)


def bulk(table):
    table.update(b=2)


tracked = Tracked()
bulk(tracked)
