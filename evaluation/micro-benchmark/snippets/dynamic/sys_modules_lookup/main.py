import sys
import commands

def local():
    pass

sys.modules["commands"].build()
sys.modules[__name__].local()
