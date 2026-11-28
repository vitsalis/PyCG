def f(): pass
def g(): pass
def h(): pass

import collections
counts = collections.Counter([f]) + collections.Counter()
counts.most_common()
ordered = collections.OrderedDict() | {}
ordered.move_to_end("a")
