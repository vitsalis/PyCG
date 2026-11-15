class Empty:
    def __bool__(self):
        return False


def fallback():
    pass


def never():
    pass


first = Empty() and never()
second = Empty() or fallback()
