
def bare():
    object.__new__().ping()
def value():
    object.__new__(5).ping()
