`property.__get__(p, obj)` runs the builtin's own `__get__` on a subclass
instance whose class overrides `__get__`: the getter runs, the override does
not.
