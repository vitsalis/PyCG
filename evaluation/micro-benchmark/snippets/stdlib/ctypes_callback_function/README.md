`ctypes.CFUNCTYPE` returns a class that it defines, `CFunctionType`.
Calling an instance of it calls that class's `__call__`, named through the
concrete class without `<locals>`
(`ctypes.CFUNCTYPE.CFunctionType.__call__`), although the class inherits
`__call__` from the C type `_ctypes.CFuncPtr`; the foreign call then runs
the Python function `double`, which belongs to `main`, whose call made it
run.
