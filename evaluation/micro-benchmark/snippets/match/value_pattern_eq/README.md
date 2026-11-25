A value pattern (`case Modes.FAST:`) compares the subject with `==`, so the match statement calls `__eq__` of the subject (an implicit call from `main`).
