import json


def load(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        return None
    return data.items()


load('{"a": 1}')
