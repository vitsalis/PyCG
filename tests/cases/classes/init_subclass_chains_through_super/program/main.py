
import ext
def f(): pass
def g(): pass

class Base:
    @classmethod
    def __init_subclass__(cls, **options):
        super().__init_subclass__(**options)
        cls.ready()
class Middle(Base):
    def __init_subclass__(cls, **options):
        super().__init_subclass__(**options)
def declare():
    class Leaf(Middle):
        @classmethod
        def ready(cls):
            pass
