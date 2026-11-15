`functools.total_ordering` adds the missing comparison methods. The generated
`__gt__` is library code that calls `__lt__` and then `!=`, which calls
`__eq__`. These calls belong to the scope that compares.
