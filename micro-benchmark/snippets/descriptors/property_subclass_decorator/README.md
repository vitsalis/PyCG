A subclass of `property` that defines no descriptor method is a property:
`@tracked` stores the getter, `.setter` and `.deleter` add the others, and a
load, a store and a deletion through an instance call them from the scope of
the access.
