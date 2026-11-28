from collections.abc import Mapping, Sequence


class Store(Mapping):
    def __getitem__(self, key): return 1
    def __iter__(self): return iter([])
    def __len__(self): return 0


class Row(Sequence):
    def __getitem__(self, index): raise IndexError
    def __len__(self): return 0


def lookup():
    "k" in Store()


def scan():
    "k" in Row()
