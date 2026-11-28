
import asyncio
class Meta(type):
    def __bool__(cls): return True
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    if C: pass
