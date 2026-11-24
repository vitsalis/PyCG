A property is created by calling `property(fget, fset, fdel)` in the class body.
The attribute is never deleted, so the edge
`main -> main.Temperature.del_celsius` must not appear.
