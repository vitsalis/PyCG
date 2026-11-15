The `__init__` that `@dataclass` generates calls the `default_factory` of a
field and then `__post_init__`. The generated `__init__` has no node, so these
calls belong to the scope that instantiates the class.
