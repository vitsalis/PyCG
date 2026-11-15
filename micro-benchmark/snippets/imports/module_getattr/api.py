def _fetch():
    pass

def __getattr__(name):
    return {"fetch": _fetch}[name]
