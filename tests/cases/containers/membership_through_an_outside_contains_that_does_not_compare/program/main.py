from collections import UserString
from collections.abc import Mapping


class Needle:
    def __eq__(self, other): return False


class Store(Mapping):
    def __getitem__(self, key): return 1
    def __iter__(self): return iter(())
    def __len__(self): return 0


class Text(str):
    pass


class Words(UserString):
    pass


class Items(list):
    pass


def lookup():
    Needle() in Store()


def search():
    Needle() in Text()


def words():
    Needle() in Words("")


def scan():
    Needle() in Items()
