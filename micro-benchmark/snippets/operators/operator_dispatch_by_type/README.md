The method that `+` calls depends on the type of the operands. `combine` only
adds `Money` objects and integers, so the edge
`main.combine -> main.Duration.__add__` must not appear.
