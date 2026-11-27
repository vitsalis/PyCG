
import asyncio
class Meta(type):
    def __hash__(cls): return 0
    def __eq__(cls, other): return True
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    {D: 1}[C]
