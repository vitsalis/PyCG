
class Right:
    def good(self): pass
class Wrong:
    def bad(self): pass
Alias = Right
class Local:
    def good(self): pass
def use(x, local, many):
    x.upper()
    local.good()
    for each in many:
        each.good()
def use_alias(alias):
    alias.good()
class C:
    Right = Wrong
    def use(self, x):
        x.good()
        x.bad()
