
def f(): pass
class Proxy:
    def __getattr__(self, name):
        return f
    def known(self): pass
def use(proxy):
    proxy.missing()
def defined(proxy):
    proxy.known()
use(Proxy())
defined(Proxy())
