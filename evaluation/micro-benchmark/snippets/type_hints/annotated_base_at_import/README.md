A class statement evaluates its bases when it runs. `TableBase` is annotated
`type[Table]`, but the assignment binds `object`, so `Database` does not
derive from `Table`: `Table.insert` runs only on the `Table` that
`Database.__getattr__` makes, and its `self.storage()` never reaches the hook.
