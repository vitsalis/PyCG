from typing import TypedDict


class Options(TypedDict):
    size: int


options = Options(size=1)
options.get("size")
