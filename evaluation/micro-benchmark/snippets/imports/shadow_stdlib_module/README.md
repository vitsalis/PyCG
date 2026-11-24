The case directory has a module `colorsys.py`, which shadows the standard library module of that name because the script directory comes first in `sys.path`.
`import colorsys` imports the local module.
