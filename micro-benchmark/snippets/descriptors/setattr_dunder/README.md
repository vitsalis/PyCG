`__setattr__` runs for every attribute assignment on an instance, also the one
in `__init__`. It delegates to `object.__setattr__` through `super()`.
