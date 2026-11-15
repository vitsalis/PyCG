`Box[int]` is a `typing._GenericAlias`, not the class. Calling it runs the
`__call__` of the alias, which instantiates `Box`, so the library calls
`Box.__init__` for the module.
