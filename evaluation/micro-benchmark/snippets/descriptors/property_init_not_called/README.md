A subclass whose `__init__` never calls `property.__init__` keeps no getter:
the load raises AttributeError and calls nothing.
