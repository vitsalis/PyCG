A subclass of `property` whose `__get__` binds the class method that it wraps
to the owner and calls it: `self.fget` is the class method that
`@classproperty` stored, and `classmethod.__get__(None, owner)` binds it to the
class of the instance. The result constructs that class.
