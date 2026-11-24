A subclass of `property` that overrides `__init__` and `__get__` and calls
`property`'s own through `super()`: the getter that `super().__init__` stored
runs inside `super().__get__`.
