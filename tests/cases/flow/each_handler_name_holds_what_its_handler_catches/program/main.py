
def f(): pass
def g(): pass
def h(): pass

import ext
class First(Exception):
    def report(self): pass
class Second(Exception):
    def report(self): pass
def use():
    try:
        ext.run()
    except First as error:
        pass
    try:
        ext.run()
    except Second as error:
        error.report()
First()
Second()
