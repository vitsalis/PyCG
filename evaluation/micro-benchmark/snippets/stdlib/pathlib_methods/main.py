import pathlib

base = pathlib.Path("data")
base.joinpath("file.txt").with_suffix(".csv")
