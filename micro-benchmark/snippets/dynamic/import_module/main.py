import importlib

name = "alpha"
plugin = importlib.import_module("plugins." + name)
plugin.run()
