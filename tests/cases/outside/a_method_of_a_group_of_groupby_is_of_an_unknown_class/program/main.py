
import itertools
for key, group in itertools.groupby([1]):
    group.__sizeof__()
