def f(): pass
def g(): pass
def h(): pass

import collections
collections.ChainMap({"a": f})["a"]()
