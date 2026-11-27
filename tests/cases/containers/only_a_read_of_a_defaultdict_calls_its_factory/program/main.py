
import collections
def make(): pass
def use(table):
    table["a"] = 1
    table.get("b")
    "c" in table
    del table["a"]
use(collections.defaultdict(make))
