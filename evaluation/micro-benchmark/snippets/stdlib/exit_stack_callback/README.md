`ExitStack.callback` registers a function, and the stack calls it when the `with` block ends. The `with` statement on a class outside the snippet adds no `__enter__` or `__exit__` edge.
