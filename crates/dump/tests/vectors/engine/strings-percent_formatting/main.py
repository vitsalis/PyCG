class Value:
    def __str__(self):
        return "str"

    def __repr__(self):
        return "repr"

v = Value()
message = "%s %r" % (v, v)
