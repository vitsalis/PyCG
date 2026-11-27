def f(): pass
def g(): pass
def h(): pass

from enum import StrEnum
class E(StrEnum):
    A = "other"
    def __hash__(self):
        return hash("pre_a")
    def __eq__(self, other):
        return other == "pre_a"

def hit(): pass
table = dict({E.A: hit})
def read(kind):
    table["pre_" + kind]()
read("a")
