`json.loads` returns a value of any type. After the guard `if not isinstance(data, dict): return None`, `data` is a dict, so `data.items()` calls `dict.items`.
