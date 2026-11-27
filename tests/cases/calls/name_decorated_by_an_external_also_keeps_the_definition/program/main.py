
import ext
@ext.task
def job(): pass
@ext.final
class Model:
    def run(self): pass
def use():
    job.delay()
    job()
    Model().run()
