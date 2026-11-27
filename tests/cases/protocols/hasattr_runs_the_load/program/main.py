
class C:
    @property
    def ready(self):
        return True
def check(c):
    return hasattr(c, "ready")
check(C())
