`isinstance` calls `__instancecheck__` of the metaclass, except when the type of
the object is exactly the class. The edge
`main.check_duck -> main.Meta.__instancecheck__` must not appear.
