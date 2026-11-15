An instance attribute shadows a method and is then deleted with `delattr`, so the same call expression `widget.render()` calls first the instance attribute and then the method.
