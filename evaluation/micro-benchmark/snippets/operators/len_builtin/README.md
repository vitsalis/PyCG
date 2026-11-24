The builtin `len` calls `__len__` of its argument. The method itself calls
`len` on a list, which runs no snippet code.
