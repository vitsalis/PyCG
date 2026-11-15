def save():
    pass

def load():
    pass

actions = frozendict(save=save, load=load)
actions["save"]()
actions.get("missing", save)()
