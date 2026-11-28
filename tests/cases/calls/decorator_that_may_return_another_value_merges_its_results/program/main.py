
def default(): pass
def register(f):
    if f is None:
        f = default
    return f
@register
def first(): pass
@register
def second(): pass
def use():
    first()
