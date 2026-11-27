
def make(): return {}
class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **options):
        mcs.check()
        return make()
    @classmethod
    def check(mcs): pass
class Model(metaclass=Meta, flag=True):
    pass
