Operations of the standard library that take an object and do not iterate
it: `itertools.repeat` gives its argument as it is, `collections.ChainMap`
keeps its mappings, and `heapq.heapify` works on the storage of a list,
also of a subclass of `list` that overrides `__iter__`. No `__iter__` or
`__next__` of the program runs, and none must appear.
