When the left operand returns `NotImplemented` (a snippet `__add__` or the
builtin `int.__add__`), Python calls the reflected method `__radd__` of the
right operand.
