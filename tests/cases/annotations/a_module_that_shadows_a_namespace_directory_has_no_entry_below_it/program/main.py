
import ns
try:
    ns.a.b.T().run()
except AttributeError:
    pass
