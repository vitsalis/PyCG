A module ships its annotations and the bases of its classes in a stub,
`mod.pyi` beside `mod.py`. Python never reads the stub. In the source, `Peek`
and `Bag` derive from nothing; the stub declares `Peek` an `Iterator[int]` and
`Bag` a `Container[int]`, and annotates `drain` with `Iterable[int]` and `has`
with `Container[int]`. Each argument comes back from a `pickle` round trip, so
data flow inside the snippet does not give its type: the stub's annotations and
bases do. `Bag` also has an `__iter__`, but `Container` is not an `Iterable`
and no code passes a `Bag` to `drain`: the edge `mod.drain -> mod.Bag.__iter__`
must not appear, and `Bag.__iter__` never runs.
