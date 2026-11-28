
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
formats.extend(["%((a))s", "%.s %r", "%(a)*s", "%s %y %r", "%d%(a)s", "%ls %(a)s"])
formats.extend([b"%r %a", b"%((a))r", b"%s %r"])
formats.extend(["%r %.2147483648s %r", b"%r %9223372036854775808r %r"])
values.extend([(Item(), Item()), {"(a)": Item(), "a": Item()}, [Item()]])
values.append({b"(a)": Item()})
