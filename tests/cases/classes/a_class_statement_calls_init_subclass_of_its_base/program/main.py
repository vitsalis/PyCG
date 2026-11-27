
import ext
def f(): pass
def g(): pass

class Plugin:
    def __init_subclass__(cls, handler=None, **options):
        handler()
        cls.setup()
    @classmethod
    def setup(cls):
        pass
class Audio(Plugin, handler=f, metaclass=type):
    @classmethod
    def setup(cls):
        pass
