
class Truth:
    def __bool__(self): return True
class Low:
    def __lt__(self, other): return Truth()
    def __eq__(self, other): return Truth()
class Answers(type):
    def __contains__(cls, value): return Truth()
    def __bool__(cls): return False
    def __getitem__(cls, index): raise IndexError
    def __setitem__(cls, key, value): pass
    def __hash__(cls): return 0
class Iterates(type):
    def __iter__(cls): return iter([Low()])
    def __await__(cls):
        yield
def late():
    return Answers
class Asked(metaclass=late()): pass
class Searched(metaclass=Iterates): pass
class Holder:
    value = Low()
class Pending:
    def __await__(self):
        yield
class Manager:
    def __aenter__(self): return Pending()
    def __aexit__(self, *args): return Pending()
async def use(value):
    async with Manager():
        pass
    await Searched
    Low() < Low() < Low()
    Low() in Asked
    Low() in Searched
    if Asked:
        pass
    for _ in Asked:
        pass
    Asked[1] = 2
    {Asked: 1}[Searched]
    "%*s" % (1, Low())
    match value:
        case Holder.value:
            pass
        case 0.5:
            pass
    match 0.5:
        case Holder.value:
            pass
