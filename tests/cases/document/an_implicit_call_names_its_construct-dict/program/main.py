class Key:
    def __hash__(self): return 0
d = {Key(): 1}
