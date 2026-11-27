import pickle

import mod

mod.drain(pickle.loads(pickle.dumps(mod.Peek())))
mod.work(pickle.loads(pickle.dumps(mod.Job())))
