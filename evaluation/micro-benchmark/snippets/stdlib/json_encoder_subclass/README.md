`json.dumps` calls the method `default` of a `json.JSONEncoder` subclass for a value that it cannot serialize. A list needs no `default`.
There is no edge from `main.dump_list` to `main.SetEncoder.default`.
