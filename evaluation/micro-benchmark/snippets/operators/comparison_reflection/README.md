The left operand of `>` has no `__gt__`, so Python calls the reflection of `>`,
which is `__lt__` of the right operand. The edge
`main -> main.Version.__gt__` must not appear.
