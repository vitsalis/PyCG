
import pathlib
from datetime import date
def use():
    date.today().isoformat()
    int.from_bytes(b"\\x01", "big").bit_length()
    pathlib.Path.cwd().joinpath("x")
