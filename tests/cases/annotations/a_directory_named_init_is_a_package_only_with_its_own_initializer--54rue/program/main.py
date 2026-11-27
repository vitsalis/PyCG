
import pkg
try:
    pkg.__init__.b.T().run()
except AttributeError:
    pass
