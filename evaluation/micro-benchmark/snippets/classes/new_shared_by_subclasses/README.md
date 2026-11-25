Two classes share a `__new__` that returns `super().__new__(cls)`, so a call
of each class gives an instance of that class alone, and a method call on it
reaches only that class's method.
