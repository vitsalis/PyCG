The generated `__init__` calls a `default_factory` only when the caller omits
the field. `Cart` receives `items`, so the edge `main -> main.new_items` must
not appear.
