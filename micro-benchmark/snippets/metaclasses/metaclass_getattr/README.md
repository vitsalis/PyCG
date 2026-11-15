`__getattr__` of the metaclass runs when an attribute lookup on the class
fails. It returns a function that the caller calls.
