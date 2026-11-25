A load through the class of a subclass instance that inherits `property`'s
`__get__`, and an explicit `__get__(None, owner)`, give the property itself: no
getter runs there, and the getter that the property holds runs where the code
calls it with an instance.
