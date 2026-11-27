
import collections
class Key:
    def __hash__(self): return 1
d = collections.OrderedDict()
d[Key()] = 1
