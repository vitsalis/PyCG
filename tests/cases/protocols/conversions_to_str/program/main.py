
class Both:
    def __str__(self): return ""
    def __repr__(self): return ""
class OnlyRepr:
    def __repr__(self): return ""
class Formatted:
    def __format__(self, spec): return ""
def as_str(both, only):
    str(both)
    print(only)
def as_repr(both, only):
    repr(both)
    f"{only!r}"
def as_format(both, formatted):
    f"{both}"
    format(formatted, "")
as_str(Both(), OnlyRepr())
as_repr(Both(), OnlyRepr())
as_format(Both(), Formatted())
