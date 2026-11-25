`self.__step()` in `Base` is mangled to `self._Base__step()`, so a subclass
method with the same private name does not override it. The edge
`main.Base.run -> main.Child.__step` must not appear.
