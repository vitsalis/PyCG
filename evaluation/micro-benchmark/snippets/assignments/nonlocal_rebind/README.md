A nested function rebinds a variable of its enclosing function through a `nonlocal` declaration before the enclosing function calls it.
Precision: there is no edge `main.outer -> main.func1`.
