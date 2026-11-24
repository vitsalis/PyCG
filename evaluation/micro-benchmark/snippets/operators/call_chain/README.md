`__call__` returns another callable instance, which is called at once:
`First()()()` instantiates `First`, calls `First.__call__`, then
`Second.__call__`.
