
import asyncio
class Meta(type):
    def __delitem__(cls, key): pass
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    del C[1]
