def f(): pass
def g(): pass
def h(): pass

import ext
map(*[f], [1])
sorted([1], **{"key": g})
ext.run(*[h], **{"done": h})
