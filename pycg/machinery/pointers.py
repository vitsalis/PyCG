class Pointer(object):
    def __init__(self):
        self.values = set()

    def add(self, item):
        self.values.add(item)

    def add_set(self, s):
        self.values = self.values.union(s)

    def get(self):
        return self.values

    def merge(self, pointer):
        self.values = self.values.union(pointer.values)

class LiteralPointer(Pointer):
    STR_LIT = "STRING"
    INT_LIT = "INTEGER"
    UNK_LIT = "UNKNOWN"

    # no need to add the actual item
    def add(self, item):
        if isinstance(item, str):
            self.values.add(self.STR_LIT)
        elif isinstance(item, int):
            self.values.add(self.INT_LIT)
        else:
            self.values.add(self.UNK_LIT)

class NamePointer(Pointer):
    def __init__(self):
        super().__init__()
        self.args = {}

    def _raise_on_invalid_arg(self, pos):
        try:
            int(pos)
        except ValueError:
            raise PointerError("Invalid position for argument")

    def get_or_create(self, pos):
        if not pos in self.args:
            self.args[pos] = set()
        return self.args[pos]

    def add_arg(self, pos, name):
        self._raise_on_invalid_arg(pos)
        self.get_or_create(pos)
        if isinstance(name, str):
            self.args[pos].add(name)
        elif isinstance(name, set):
            self.args[pos]= self.args[pos].union(name)
        else:
            raise Exception()

    def add_lit_arg(self, pos, item):
        self._raise_on_invalid_arg(pos)
        arg = self.get_or_create(pos)
        if isinstance(item, str):
            self.args[pos].add(LiteralPointer.STR_LIT)
        elif isinstance(item, int):
            self.args[pos].add(LiteralPointer.INT_LIT)
        else:
            self.args[pos].add(LiteralPointer.UNK_LIT)

    def get_arg(self, pos):
        if self.args.get(pos, None):
            return self.args[pos]

    def get_args(self):
        return self.args

class PointerError(Exception):
    pass
