Binary operators call the matching method of the left operand (`+` calls
`__add__`, `@` calls `__matmul__`). No subtraction runs, so the edge
`main -> main.Vector.__sub__` must not appear.
