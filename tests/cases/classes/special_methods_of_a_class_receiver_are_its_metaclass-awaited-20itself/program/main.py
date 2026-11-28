
import asyncio
class Meta(type):
    pass
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    (await asyncio.sleep(0, C)).run()
