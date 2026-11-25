`super().close()` in `Leaf` finds no `close` in the direct parent `Middle` and
continues the lookup to `Base`.
