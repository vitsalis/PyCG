import sys
__lazy_modules__ = ["json", "os"]
import json
import os
from os import path
def reads_locals():
    return locals()
def reads_vars(obj):
    return vars(obj), vars()
def runs(code):
    exec(code)
module = sys.modules[__name__]
print(globals())
def shadow(eval):
    return eval("1")
