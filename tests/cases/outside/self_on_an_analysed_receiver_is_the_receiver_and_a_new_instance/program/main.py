
import pathlib
class Local(pathlib.PurePosixPath):
    def mark(self): pass
def tag(): pass
def use(path):
    path.tag = tag
    copy = path.with_suffix(".x")
    copy.tag()
    copy.mark()
use(Local("a"))
