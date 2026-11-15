`item` is a `Text` or an `Image`. A `Text` never reaches the branch where `isinstance(item, Text)` is false, so `item.render()` calls `Image.render` only.
