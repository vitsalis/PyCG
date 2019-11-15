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
        self.pos_to_name = {}
        self.args = {}

    def _sanitize_pos(self, pos):
        try:
            int(pos)
        except ValueError:
            raise PointerError("Invalid position for argument")

        return pos

    def get_or_create(self, name):
        if not name in self.args:
            self.args[name] = set()
        return self.args[name]

    def add_arg(self, name, item):
        arg = self.get_or_create(name)
        if isinstance(item, str):
            self.args[name].add(item)
        elif isinstance(item, set):
            self.args[name] = self.args[name].union(item)
        else:
            raise Exception()

    def add_lit_arg(self, name, item):
        arg = self.get_or_create(name)
        if isinstance(item, str):
            arg.add(LiteralPointer.STR_LIT)
        elif isinstance(item, int):
            arg.add(LiteralPointer.INT_LIT)
        else:
            arg.add(LiteralPointer.UNK_LIT)

    def add_pos_arg(self, pos, name, item):
        pos = self._sanitize_pos(pos)
        if not name:
            if self.pos_to_name.get(pos, None):
                name = self.pos_to_name[pos]
            else:
                name = str(pos)
        self.pos_to_name[pos] = name
        self.add_arg(name, item)

    def add_pos_lit_arg(self, pos, name, item):
        pos = self._sanitize_pos(pos)
        if not name:
            name = str(pos)
        self.pos_to_name[pos] = name
        self.add_lit_arg(name, item)

    def get_pos_arg(self, pos):
        pos = self._sanitize_pos(pos)
        name = self.pos_to_name.get(pos, None)
        return self.get_arg(name)

    def get_arg(self, name):
        if self.args.get(name, None):
            return self.args[name]

    def get_args(self):
        return self.args

    def get_pos_args(self):
        args = {}
        for pos, name in self.pos_to_name.items():
            args[pos] = self.args[name]
        return args

    def get_pos_names(self):
        return self.pos_to_name

    def merge(self, pointer):
        super().merge(pointer)
        if hasattr(pointer, "get_pos_names"):
            for pos, name in pointer.get_pos_names().items():
                self.pos_to_name[pos] = name
            for name, arg in pointer.get_args().items():
                self.add_arg(name, arg)

class PointerError(Exception):
    pass
