import lib
@lib.task()
def job(): pass
@lib.task()
class Model:
    def run(self): pass
def use():
    job()
    Model().run()
