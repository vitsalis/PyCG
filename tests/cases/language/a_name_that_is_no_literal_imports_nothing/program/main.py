
import importlib
name = "plugins.alpha"
importlib.import_module(name).run()
importlib.import_module("plugins." + "beta").run()
