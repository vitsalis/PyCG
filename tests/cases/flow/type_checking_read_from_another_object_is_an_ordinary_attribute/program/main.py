
def f(): pass
def g(): pass
def h(): pass

class Config:
    TYPE_CHECKING = True
class Holder:
    config = Config
if Holder.config.TYPE_CHECKING:
    f()
