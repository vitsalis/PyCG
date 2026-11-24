A `collections.UserDict` subclass overrides `__setitem__`. Unlike `dict.update`,
the inherited Python `update` calls `__setitem__`, so the library call belongs
to `bulk`.
