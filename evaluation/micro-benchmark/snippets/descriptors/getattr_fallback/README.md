`__getattr__` runs only when normal lookup fails, and here returns a function
that the caller calls. `known` exists, so the edge
`main.use_known -> main.Proxy.__getattr__` must not appear.
