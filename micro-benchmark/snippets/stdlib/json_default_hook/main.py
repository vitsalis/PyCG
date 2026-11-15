import json

def encode(value):
    return sorted(value)

json.dumps({1, 2}, default=encode)
