`finally` runs after the `return` in the `try` block has evaluated its value.
The code after the `try` statement is dead, so the edge
`main.compute -> main.never` must not appear.
