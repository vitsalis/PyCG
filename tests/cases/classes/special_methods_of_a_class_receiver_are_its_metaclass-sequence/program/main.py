
import asyncio
class Meta(type):
    def __getitem__(cls, index): raise IndexError
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    for _ in C: pass
