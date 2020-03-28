class ModuleManager:
    def __init__(self):
        self.internal = {}
        self.external = {}

    def create(self, name, fname, external=False):
        mod = Module(name, fname)
        if external:
            self.external[name] = mod
        else:
            self.internal[name] = mod
        return mod

    def get(self, name):
        if name in self.internal:
            return self.internal[name]
        if name in self.external:
            return self.external[name]

    def get_internal_modules(self):
        return self.internal

    def get_external_modules(self):
        return self.external

class Module:
    def __init__(self, name, filename):
        self.name = name
        self.filename = filename
        self.methods = set()
        self.methods.add(name)

    def get_name(self):
        return self.name

    def get_filename(self):
        return self.filename

    def get_methods(self):
        return list(self.methods)

    def add_method(self, method):
        self.methods.add(method)
