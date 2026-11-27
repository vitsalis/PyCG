
class M1(type):
    def __await__(cls): yield
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta):
        def done(self): pass
    async def run():
        result = await Bag
        result.done(result)
    run()
for meta in (M1, M2, M3):
    use(meta)
