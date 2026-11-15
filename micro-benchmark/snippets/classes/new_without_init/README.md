A class defines `__new__` and no `__init__`. Instantiation calls `__new__`, which
calls `object.__new__` through `super()`.
