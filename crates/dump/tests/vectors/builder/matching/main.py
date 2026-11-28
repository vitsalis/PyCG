class P:
    __match_args__ = ('x', 'y')
def f(v, kind):
    match v:
        case 1 | 2 if kind:
            r = 'small'
        case None:
            r = None
        case [first, *rest, last]:
            r = rest
        case (a, b):
            r = a
        case {'k': k, **others}:
            r = others
        case P(px, y=py) as point:
            r = point
        case int(n) | str(n):
            r = n
        case _:
            r = v
    return r
match 3:
    case 3:
        three = True
    case 4:
        four = True
match 'a':
    case True:
        t = 1
    case [x]:
        t = x
