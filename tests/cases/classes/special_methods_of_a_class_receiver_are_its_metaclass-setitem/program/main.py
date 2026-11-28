
import asyncio
class Meta(type):
    def __setitem__(cls, key, value): pass
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    C[1] = 2
