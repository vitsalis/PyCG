The class defines `__eq__` and no `__ne__`. The inherited `object.__ne__` calls
`__eq__` and inverts the result.
