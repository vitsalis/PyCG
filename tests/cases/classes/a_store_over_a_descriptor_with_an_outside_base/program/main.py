
import os
import sys
from unittest import mock
import somelib
def f(): pass
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class X4: pass
class Y4: pass
class Data(mock.PropertyMock): pass
class Unknown(somelib.Base): pass
class Number(int): pass
class Function(os.getcwd): pass
class Exhaustive(
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
    X4 if sys.argv else Y4,
):
    pass
class C:
    data = Data()
    unknown = Unknown()
    number = Number()
    function = Function()
    exhaustive = Exhaustive()
def data(c):
    c.data = f
    c.data()
def unknown(c):
    c.unknown = f
    c.unknown()
def number(c):
    c.number = f
    c.number()
def function(c):
    c.function = f
    c.function()
def exhaustive(c):
    c.exhaustive = f
    c.exhaustive()
for use in (data, unknown, number, function, exhaustive):
    use(C())
