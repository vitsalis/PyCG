`str()`, `format()` and f-strings fall back to `__repr__` only when no class
of the MRO before `object` defines `__str__`. `str` and `Exception` define
it, so the `__repr__` of `Name` and `Failure` is never called; `int` does
not, so `str(Count(1))` and `f"{Count(1)}"` call `Count.__repr__`.
