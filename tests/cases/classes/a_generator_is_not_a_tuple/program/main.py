class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

def made():
    yield A()
async def made_async():
    yield Sub()
def parse(arg):
    if isinstance(arg, tuple):
        for value in arg:
            value.inside()
async def parse_async(arg):
    if isinstance(arg, tuple):
        async for value in arg:
            value.inside()
    elif isinstance(arg, list):
        async for value in arg:
            value.after()
parse(made())
parse((B(),))
parse_async(made_async())
