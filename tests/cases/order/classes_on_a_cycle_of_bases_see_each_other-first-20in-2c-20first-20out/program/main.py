
Left = Right = object
class P(Right):
    def p(self): pass
class Q(Left):
    pass
def swap():
    global Left, Right
    Left, Right = P, Q
Q().p()
