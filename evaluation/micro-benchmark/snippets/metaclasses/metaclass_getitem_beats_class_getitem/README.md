Subscripting a class calls `__getitem__` of its metaclass if there is one;
`__class_getitem__` is only the fallback. The edge
`main -> main.Palette.__class_getitem__` must not appear.
