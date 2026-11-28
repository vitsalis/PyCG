
class Needle:
    def __eq__(self, other): return True
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return 1
        raise IndexError
def make():
    return 1
class Blank:
    def __getitem__(self, index):
        return None
def blank():
    return None
def use():
    xs = list(iter(Blank()))
    Needle() in xs
