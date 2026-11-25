import operator

def save():
    pass

def load():
    pass

actions = {"save": save, "load": load}
operator.itemgetter("save")(actions)()
