`str()` and `print` call `__str__`; `repr()` and the `!r` conversion call
`__repr__`. Without `__str__`, `str()` falls back to `__repr__`.
