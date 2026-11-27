import lib
@lib.first()
@lib.second()
def job(): pass
@lib.first()
@lib.second()
class Model:
    def run(self): pass
def use():
    job()
    Model().run()
