import abc
def abstractmethod(funcobj):
    return funcobj
def target():
    pass
abstractmethod(*(target,))
abc.abstractmethod(*(target,))
