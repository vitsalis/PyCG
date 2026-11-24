import pickle

import mod

mod.drain(pickle.loads(pickle.dumps(mod.Peek())))
mod.has(pickle.loads(pickle.dumps(mod.Bag())))
