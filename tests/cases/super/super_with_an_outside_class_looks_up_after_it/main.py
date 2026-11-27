
class Mixin:
    def __init__(self): pass
class Results(dict, Mixin):
    def __init__(self):
        super(dict, self).__init__()
Results()
