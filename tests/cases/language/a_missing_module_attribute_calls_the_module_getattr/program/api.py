
def _fetch(): pass
def present(): pass
def __getattr__(name):
    return {"fetch": _fetch, "later": _fetch}[name]
