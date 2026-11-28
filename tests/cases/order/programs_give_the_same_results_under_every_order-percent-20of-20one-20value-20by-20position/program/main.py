
class Item:
    def __repr__(self): return "item"
    def __str__(self): return "s"
formats = []
values = []
for fmt in formats:
    for value in values:
        try:
            fmt % value
        except (TypeError, ValueError):
            pass
formats.extend(["%*s", "%d%s", "%s%s", "%s%(a)s", "%(a)s%s"])
values.extend([[Item()], Item(), {"a": Item()}])
