
def register(cls):
    cls.extra = helper
    return cls
def helper(self): pass
@register
class C:
    def __init__(self): pass
C().extra()
