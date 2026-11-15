`shape` is a `Circle` or a `Square`, but only a `Circle` reaches the branch where `isinstance(shape, Circle)` holds, so `shape.area()` calls `Circle.area` only.
