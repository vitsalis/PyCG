An instance of an iterator class (a class with `__iter__` and `__next__`, not a
generator) is passed as a parameter. The function iterates over it, which calls
`__iter__` and `__next__` implicitly. `__next__` returns the function `func`,
which is not called.
