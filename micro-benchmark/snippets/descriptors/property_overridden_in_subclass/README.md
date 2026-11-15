A subclass overrides a property. Reading it on a subclass instance calls only
the subclass getter, so the edge `main -> main.Shape.name` must not appear.
