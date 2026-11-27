
class Record:
    @property
    def a(self): pass
    @property
    def b(self): pass
    @property
    def c(self): pass
    @property
    def d(self): pass
    @property
    def e(self): pass

def run(record):
    for name in ("a", "b", "c", "d", "e"):
        getattr(record, name)
run(Record())
