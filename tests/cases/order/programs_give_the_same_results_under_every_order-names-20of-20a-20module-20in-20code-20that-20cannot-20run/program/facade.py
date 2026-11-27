
from lib import *
def other(): pass
def __getattr__(name):
    return other
