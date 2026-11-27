
def first(): pass
def fallback(): pass
def choose(candidate, default):
    enabled = False
    return (candidate and enabled) or default
choose(first, fallback)()
