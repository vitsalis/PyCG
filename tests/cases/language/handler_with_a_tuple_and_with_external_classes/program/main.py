
import ext
class A(Exception):
    def a(self): pass
class B(Exception):
    def b(self): pass
def run():
    raise A()
    raise B()
try:
    run()
except (A, B) as error:
    error.a()
    error.b()
except ext.Error as error:
    error.details()
