
class Defaults(dict):
    def __missing__(self, key):
        return key
class Own(dict):
    def __getitem__(self, key):
        return key
    def __missing__(self, key):
        return key
def use(a, b):
    a["x"]
    a.get("y")
    b["x"]
use(Defaults(), Own())
