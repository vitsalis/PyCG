
class Audited:
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
class Clone:
    def __init__(self, value): pass
    def copy(self):
        return self.__class__(1)
Audited().x = 1
Clone(0).copy()
