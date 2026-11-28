
def g(): pass
def h(): pass
class C:
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new):
        new()
        self._value = h
c = C()
c.value = g
c.value()
