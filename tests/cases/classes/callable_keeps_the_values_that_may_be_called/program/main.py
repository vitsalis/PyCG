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

import os
class Action:
    def __call__(self): pass
    def inside(self): pass
class Made:
    def __init__(self): pass
    def after(self): pass
def task(): pass
def run(value):
    if callable(value):
        value.inside()
        value()
    else:
        value.after()
def guard(value):
    if not callable(value):
        return
    value()
for value in (task, Action(), A(), [A()], "a", os, len, Made):
    run(value)
    guard(value)
