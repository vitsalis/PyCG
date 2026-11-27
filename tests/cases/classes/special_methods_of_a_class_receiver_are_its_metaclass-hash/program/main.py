
import asyncio
class Meta(type):
    def __hash__(cls): return 0
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    {C: 1}
