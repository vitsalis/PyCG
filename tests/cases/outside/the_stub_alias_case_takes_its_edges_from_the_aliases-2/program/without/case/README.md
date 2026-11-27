A module ships its annotations in a stub, `mod.pyi` beside `mod.py`. Python
never reads the stub. The stub binds `drain = _drain`, so `drain` has the
signature of `_drain`, whose parameter is an `Iterable[int]`; it declares
`Peek` an `Iterator[int]`. It annotates `work` with `MaybeJob`, an alias of
`Job | None`. Each argument comes back from a `pickle` round trip, so data
flow inside the snippet does not give its type: the stub's aliases do.
`_drain` exists only in the stub.
