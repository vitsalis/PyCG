
TABLE = []
def register(f):
    TABLE.append(f)
    return f
@register
def first(): pass
@register
def second(): pass
def use():
    first()
