An inherited method calls hooks through `self`. One hook is overridden in the
subclass, so the edge `main.Pipeline.run -> main.Pipeline.transform` must not
appear.
