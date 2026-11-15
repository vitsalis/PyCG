A class without `__iter__` but with `__getitem__` is iterable: the `for` loop
calls `__getitem__` with 0, 1, 2, ... until it raises `IndexError`.
