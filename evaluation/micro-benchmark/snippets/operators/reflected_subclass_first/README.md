If the right operand is an instance of a subclass that overrides the reflected
method, Python calls `__radd__` of the right operand first. It returns a value,
so the edge `main -> main.Base.__add__` must not appear.
