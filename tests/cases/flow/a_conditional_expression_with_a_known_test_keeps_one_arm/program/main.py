
def f(): pass
def g(): pass
def h(): pass

import ext
verbose = True
quiet = not verbose
empty = ()
(f if verbose else g)()
(f if quiet else g)()
(h if empty else g)()
def use():
    (f if verbose else g)()
