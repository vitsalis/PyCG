`@dataclass(order=True)` generates comparison methods that compare tuples of the
fields. The tuple comparison calls `__eq__` and then `__lt__` of the field
objects. The generated methods have no node, so the calls belong to the scope
that calls `sorted`.
