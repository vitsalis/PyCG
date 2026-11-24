A subclass of `property` called with a getter and a setter in a class body
keeps both: the store calls the setter and the load calls the getter, each from
the function that accesses the attribute. Constructing the property calls
neither.
