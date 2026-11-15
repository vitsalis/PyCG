A `class` statement with a metaclass calls the metaclass `__new__` and
`__init__`, also for a subclass that inherits the metaclass. They delegate to
`type` through `super()`.
