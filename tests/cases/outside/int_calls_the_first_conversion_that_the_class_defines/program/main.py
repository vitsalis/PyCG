
class Number:
    def __int__(self): return 1
    def __index__(self): return 2
class Index:
    def __index__(self): return 2
int(Number())
int(Index())
