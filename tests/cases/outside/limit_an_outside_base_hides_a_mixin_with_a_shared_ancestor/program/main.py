
from collections import UserDict
from collections.abc import MutableMapping
class Mixin(MutableMapping):
    def popitem(self):
        return ("x", None)
class C(UserDict, Mixin):
    pass
C().popitem()
