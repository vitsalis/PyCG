
import collections
class Cache:
    def get(self): pass
    def clear(self): pass
def read(table):
    return table["k"]
def run(obj, command):
    getattr(obj, command.__name__)()
factories = []
first = collections.defaultdict(factories[0])
read(first)()
read(first.copy())()
read(collections.defaultdict(Cache)).get()
factories.append(Cache().clear)
commands = []
def use():
    for command in commands:
        run(LATE, command)
use()
commands.append(Cache.get)
def renamed(): pass
renamed.__name__ = "clear"
commands.append(renamed)
LATE = Cache()
