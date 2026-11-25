Operations of the standard library that iterate their arguments at the
call: `itertools.product` makes a tuple of its argument where it is made,
so `make` advances the iterator and `consume`, which advances the product,
calls no method of the program. `functools.reduce` and `math.sumprod`
iterate where they are called. The classes define no `__len__`, so the
length hint that `product` asks on Python 3.12 and 3.13 calls nothing of
the program.
