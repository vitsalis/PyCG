A function and a `__new__` that return `args[0]` give each call its own
first argument back.
Precision: there is no edge `main -> main.func2` and no edge
`main -> main.Right.run`.
