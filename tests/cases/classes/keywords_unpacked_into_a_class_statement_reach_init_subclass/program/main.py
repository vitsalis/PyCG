
import ext
def f(): pass
def g(): pass

class Plugin:
    def __init_subclass__(cls, **options):
        options["handler"]()
options = {"handler": f}
class Audio(Plugin, **options):
    pass
