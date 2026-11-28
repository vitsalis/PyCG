
import pkg
def use(x, y, z):
    pass
try:
    pkg.native.run()
except AttributeError:
    pass
