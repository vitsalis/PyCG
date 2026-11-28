class Keys:
    taken = 'taken'
    keep = 'pre_a'
def consumed(): pass
def target(): pass
def use(taken, **kw):
    kind = 'a'
    kw['pre_' + kind]()
use(**{Keys.taken: consumed, Keys.keep: target})
