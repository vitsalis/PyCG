
class Money:
    def __format__(self, spec): return "1"
class User:
    @property
    def name(self): return "ada"
    def __repr__(self): return "u"
def use(m, u):
    "{:>8} {}".format(m, u.name)
    "{0.name} {who!r}".format(u, who=u)
use(Money(), User())
