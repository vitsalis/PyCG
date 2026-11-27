
import pathlib
class Location(pathlib.PurePosixPath):
    pass
def rename(path):
    return path.with_suffix(".txt")
first = rename(Location("a"))
rename(Location("b")); rename(Location("c"))
