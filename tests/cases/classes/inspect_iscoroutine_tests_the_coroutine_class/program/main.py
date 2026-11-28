class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

import inspect
from inspect import iscoroutine
import inspect as introspection
async def run():
    return 1
def through_name(result):
    if iscoroutine(result):
        result.close()
    else:
        result.inside()
def through_module(result):
    if not inspect.iscoroutine(result):
        result.inside()
def through_alias(result):
    if introspection.iscoroutine(result):
        result.inside()
def rebound(result, iscoroutine=bool):
    if iscoroutine(result):
        result.inside()
for function in (through_name, through_module, through_alias, rebound):
    function(run())
    function(A())
