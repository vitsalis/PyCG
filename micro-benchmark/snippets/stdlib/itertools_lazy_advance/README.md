Lazy objects of `itertools`: `islice`, `takewhile` and `cycle` call
`iter()` on their argument where they are made and advance its iterator
only where they are advanced. `make` makes an `islice` that `consume`
advances: the `__next__` calls belong to `consume`. `returned` makes a
`takewhile` that nothing advances: it calls `Source.__iter__` and no
`Countdown.__next__`. `step` advances a `cycle` once with `next()`.
The iterable (`Source`) and its iterator (`Countdown`) are different
objects, so where each method runs shows.
