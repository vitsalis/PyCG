class plain(property):
    pass


class Doc:
    @plain
    def text(self):
        return "x"

    @property
    def size(self):
        return 1


def read_class():
    return Doc.text


def read_explicit():
    return Doc.__dict__["size"].__get__(None, Doc)


def use(prop):
    return prop.fget(Doc())


use(read_class())
use(read_explicit())
