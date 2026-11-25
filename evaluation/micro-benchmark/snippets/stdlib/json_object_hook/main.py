import json

def decode(obj):
    return obj

json.loads('{"a": 1}', object_hook=decode)
