An attribute lookup on an instance falls back to a class attribute of the base
class. A sibling subclass replaces the attribute but is never used, so the edge
`main -> main.custom_handler` must not appear.
