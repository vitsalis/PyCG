
def key(x):
    return x
def fallback(): pass
max([1], **{"key": key, "default": fallback})
