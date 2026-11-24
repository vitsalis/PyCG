A subclass that defines its own `__set__` and `__delete__`: a store and a
deletion run those, and the setter and deleter that the property holds never
run.
