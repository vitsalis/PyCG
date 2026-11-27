match p:
    case C(1, a=2) | [1, *r]:
        pass
    case {'k': v, **rest}:
        pass
    case None | True:
        pass
    case (x as y) if y:
        pass
