A module that names `audit` in `__lazy_modules__` (PEP 810, Python 3.15) imports it lazily with a plain `import`. `audit` is never used, so it never runs and is not a node. Older versions ignore `__lazy_modules__` and run `audit`.
There is no edge to `audit.record`.
