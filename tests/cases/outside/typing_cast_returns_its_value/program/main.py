
import typing
class Base:
    def run(self): pass
class Impl(Base):
    def run(self): pass
def execute(obj):
    typing.cast(Base, obj).run()
execute(Impl())
