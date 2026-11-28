class C:
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
    @property
    def value(self): pass
    @value.setter
    def value(self, new): pass
