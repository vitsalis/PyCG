
from importlib import import_module
class Local:
    def run(self): pass
def local_loader(name):
    return Local()
def load(import_module):
    import_module("json").run()
load(local_loader)
