
import ext
def done(): pass
def use():
    ext.loop.task.add_done_callback(done)
