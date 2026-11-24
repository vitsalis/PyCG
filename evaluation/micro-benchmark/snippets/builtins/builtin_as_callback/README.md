Builtin functions are passed as callbacks to other builtins. Only call expressions count for builtins, and the snippet does not call `len` or `str.upper` itself.
There is no edge to `<builtin>.len` or `<builtin>.str.upper`.
