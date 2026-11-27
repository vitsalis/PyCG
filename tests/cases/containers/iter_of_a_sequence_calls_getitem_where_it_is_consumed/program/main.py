
def target(): pass
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return target
        raise IndexError
def make():
    return iter(Seq())
def use(iterator):
    for f in iterator:
        f()
def first():
    return next(iter(Seq()))
async def drain(seq):
    async for f in seq:
        pass
use(make())
first()()
drain(Seq())
