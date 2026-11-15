import collections

counts = collections.Counter("abca")
counts.update("b")
counts.most_common(1)
