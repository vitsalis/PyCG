
def register(f):
    f = f or None
    return f
@register
def first(): pass
@register
def second(): pass
def use():
    first()
