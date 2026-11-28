import lib
deco = lib.task()
@deco
def job(): pass
deco = lib.task()
@deco
class Model:
    def run(self): pass
def use():
    job()
    Model().run()
