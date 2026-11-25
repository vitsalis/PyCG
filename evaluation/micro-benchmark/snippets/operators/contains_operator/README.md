`in` and `not in` call `__contains__` of the right operand. The class defines
it, so the edge `main -> main.Inventory.__iter__` must not appear.
