class Lock:
    def __enter__(self): pass
    def __exit__(self, *args): pass
with Lock():
    pass
