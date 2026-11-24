An instance of an iterator class (not a generator) is created but never
iterated over, so `__iter__` and `__next__` do not run. `__next__` returns the
name `func`, which the module does not define. This causes no error, because
the method never runs.
