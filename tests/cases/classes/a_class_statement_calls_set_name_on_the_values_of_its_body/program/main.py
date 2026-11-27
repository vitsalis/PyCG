
import ext
def f(): pass
def g(): pass

class Field:
    def __set_name__(self, owner, name):
        owner.declare()
class Plain:
    pass
def build():
    class Model:
        title = Field()
        other = Plain()
        @classmethod
        def declare(cls):
            pass
