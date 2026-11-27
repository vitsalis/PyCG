
import ext
def f(): pass
def g(): pass

import builtins
def bare():
    exit(1)
def through_module():
    builtins.quit(1)
if exit is not None:
    help()
