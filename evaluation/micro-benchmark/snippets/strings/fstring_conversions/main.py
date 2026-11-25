class Value:
    def __str__(self):
        return "str"

    def __repr__(self):
        return "repr"

    def __format__(self, spec):
        return "format"

v = Value()
message = f"{v!s} {v!r} {v}"
