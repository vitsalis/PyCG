
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

def by_dict(record):
    for name in Record.__dict__:
        getattr(record, name)
def by_vars(record):
    for name in vars(Record):
        getattr(record, name)
by_dict(Record())
by_vars(Record())
