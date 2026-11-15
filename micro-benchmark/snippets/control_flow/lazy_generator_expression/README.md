The first iterable of a generator expression is evaluated when the expression is created; the element expression only when the generator is consumed, which never happens. The call `f()` never runs.
Precision: there is no edge `main -> main.func1`.
