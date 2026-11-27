
import lib, dynamic, facade, proxy
def dead():
    lib.absent()
def type_only():
    lib.Sequence()
def deleted():
    lib.temporary()
def present():
    lib.present()
def namespace():
    dynamic.absent()
def star():
    facade.absent()
def star_present():
    facade.present()
def method():
    proxy.Proxy().method()
def inherited():
    proxy.Proxy().inherited()
