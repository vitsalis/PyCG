
import concurrent.futures
import multiprocessing
bases = [multiprocessing.reduction.AbstractReducer]
class Reducer(bases[0]): pass
bases[0] = Reducer.ForkingPickler
class Task(concurrent.futures._base.Future): pass
Task().done()
Reducer().dump(1)
