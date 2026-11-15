`reversed()` calls `__reversed__`. Without it, it uses `__len__` and
`__getitem__`. `Deck` defines `__reversed__`, so the edge
`main -> main.Deck.__len__` must not appear.
