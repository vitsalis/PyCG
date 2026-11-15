import json

def freeze(items):
    return tuple(items)

json.loads("[1, [2]]", array_hook=freeze)
