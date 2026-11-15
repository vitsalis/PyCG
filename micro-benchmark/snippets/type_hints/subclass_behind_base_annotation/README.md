A parameter is annotated with a base class and receives a subclass instance
that overrides the method. The annotation alone points to the wrong method: the
edge `main.talk -> main.Animal.speak` must not appear.
