`%` formatting with a format string that a variable holds. The `%r`
conversion calls `__repr__` of the item. `main.Node.__str__` is never called.
