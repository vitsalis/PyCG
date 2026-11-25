A foreign function of a `ctypes.CDLL` is an instance of the class
`_FuncPtr` that `CDLL.__init__` defines for each library. Calling it calls
that class's `__call__`, named through the concrete class without
`<locals>` (`ctypes.CDLL.__init__._FuncPtr.__call__`), although the class
inherits `__call__` from the C type `_ctypes.CFuncPtr`. Requires a C
library that `dlopen(NULL)` exposes, as on Linux and macOS.
