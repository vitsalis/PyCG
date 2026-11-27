
from lib import Base
class Hooked:
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
class Mine(Base):
    pass
def use(mine):
    mine.handler.run()
    mine.other = 1
use(Mine())
