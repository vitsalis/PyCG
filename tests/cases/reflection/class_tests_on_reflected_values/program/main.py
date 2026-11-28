
import inspect
class C:
    def f(self): pass
def namespace_is_dict():
    ns = vars(C)
    if isinstance(ns, dict):
        ns["f"](C())
def namespace_is_not_dict():
    ns = vars(C)
    if not isinstance(ns, dict):
        ns["f"](C())
def members_are_not_a_list():
    found = inspect.getmembers(C)
    if not isinstance(found, list):
        for name, value in found:
            value(C())
def pairs_are_not_tuples():
    for pair in inspect.getmembers(C):
        if not isinstance(pair, tuple):
            pair[1](C())
def pairs_are_tuples():
    for pair in inspect.getmembers(C):
        if isinstance(pair, tuple):
            pair[1](C())
namespace_is_dict()
namespace_is_not_dict()
members_are_not_a_list()
pairs_are_not_tuples()
pairs_are_tuples()
