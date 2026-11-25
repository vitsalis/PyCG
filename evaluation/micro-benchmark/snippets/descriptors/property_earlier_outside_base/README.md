A class derived from `functools.cached_property` and then `property`:
`cached_property`'s `__init__` and `__get__` come first in the MRO, so the load
calls the method as `cached_property` does, not as a property.
