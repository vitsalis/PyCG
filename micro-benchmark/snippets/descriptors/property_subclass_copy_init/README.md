`prop.setter(write)` on a subclass instance makes the copy by calling the
subclass with four arguments: its own `__init__` runs, from the function that
calls `setter`.
