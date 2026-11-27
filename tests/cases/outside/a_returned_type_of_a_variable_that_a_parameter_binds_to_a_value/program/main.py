
import enum
class E(enum.Enum):
    X = 1
    def ping(self): pass
enum.pickle_by_enum_name(E.X, 2)[1][0].X.ping()
