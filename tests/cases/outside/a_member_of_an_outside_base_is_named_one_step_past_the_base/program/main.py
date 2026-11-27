
import concurrent.futures
import multiprocessing
class Task(concurrent.futures._base.Future): pass
class Reducer(multiprocessing.reduction.AbstractReducer): pass
class Pickler(Reducer.ForkingPickler): pass
def use():
    Task().done()
    Pickler(None).dump(1)
