Creating a subclass calls `__init_subclass__` of its base, from the scope that
runs the `class` statement. It calls `object.__init_subclass__` through
`super()`.
