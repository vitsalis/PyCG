A slot is a descriptor on the class, so a load of a slot that holds a value
finds it and does not call `__getattr__`. The edges
`main.Lazy.run -> main.Lazy.__getattr__` and `main.Lazy.run -> main.fallback`
must not appear.
