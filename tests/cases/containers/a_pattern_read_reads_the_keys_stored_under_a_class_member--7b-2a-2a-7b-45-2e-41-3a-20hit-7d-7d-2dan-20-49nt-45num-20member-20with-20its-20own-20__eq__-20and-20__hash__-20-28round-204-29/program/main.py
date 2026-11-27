def f(): pass
def g(): pass
def h(): pass

from enum import IntEnum
class E(IntEnum):
    A = 1
    def __hash__(self):
        return hash("pre_a")
    def __eq__(self, other):
        return other == "pre_a"

def hit(): pass
table = {**{E.A: hit}}
def read(kind):
    table["pre_" + kind]()
read("a")
