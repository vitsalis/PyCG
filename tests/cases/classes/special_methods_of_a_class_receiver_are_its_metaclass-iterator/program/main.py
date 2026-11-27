
import asyncio
class Meta(type):
    def __iter__(cls): return cls
    def __next__(cls): raise StopIteration
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    for _ in C: pass
