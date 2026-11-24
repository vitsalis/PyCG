An abstract base class declares an abstract method and calls it from a concrete
method; a subclass implements it. The abstract body never runs, so the edge
`main.Shape.describe -> main.Shape.area` must not appear.
