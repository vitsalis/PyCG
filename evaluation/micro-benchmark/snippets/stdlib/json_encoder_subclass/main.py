import json

class SetEncoder(json.JSONEncoder):
    def default(self, value):
        return sorted(value)

def dump_set():
    json.dumps({"b", "a"}, cls=SetEncoder)

def dump_list():
    json.dumps([1, 2], cls=SetEncoder)

dump_set()
dump_list()
