A class that derives from `collections.abc.Iterator` inherits `__iter__`, which returns the instance itself, so a `for` loop calls the class's `__next__` and the function that it returns.
