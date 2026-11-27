class It:
    def __init__(self, *args): pass
It.__init__ = classmethod(It)
It()
