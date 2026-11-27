
class Opts:
    def __init__(self, meta): pass
class Schema:
    OPTIONS_CLASS: type = Opts
    KIND: type | None = None
    def make(self, meta: type, known: type[Opts]):
        self.OPTIONS_CLASS(meta)
        self.KIND()
        meta()
        meta.mro()
        known(meta)
