class C:
    def __format__(self, spec): return ""
f"{C()}"
