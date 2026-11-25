The keys of a class's `__dict__` are the names that its body binds. A
`getattr` over them loads each one, here five properties, more than the four
computed names that a name of another origin may hold.
