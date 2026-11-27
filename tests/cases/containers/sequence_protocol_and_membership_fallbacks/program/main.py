
def target(): pass
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return target
        raise IndexError
class Both:
    def __iter__(self):
        return iter([])
    def __getitem__(self, index): pass
class Searchable:
    def __iter__(self):
        return iter([target])
class Contains:
    def __contains__(self, item): return True
    def __iter__(self): pass
def use():
    for f in Seq():
        f()
    for x in Both():
        pass
    target in Searchable()
    target in Contains()
