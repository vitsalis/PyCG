A custom exception defines `__str__`. Both `str(error)` and the f-string call
it. Raising the class without parentheses instantiates it with the `__init__`
inherited from `Exception`.
