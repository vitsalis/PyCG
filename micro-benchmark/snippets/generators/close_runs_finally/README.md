`close()` on a suspended generator raises `GeneratorExit` at the `yield`, so the `finally` block of the generator runs and calls a function.
