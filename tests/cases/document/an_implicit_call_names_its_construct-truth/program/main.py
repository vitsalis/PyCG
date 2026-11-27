class C:
    def __bool__(self): return True
if C():
    pass
