`and` and `or` call `__bool__` of the left operand and evaluate the right
operand only when needed. The left operand is false, so the edge
`main -> main.never` must not appear.
