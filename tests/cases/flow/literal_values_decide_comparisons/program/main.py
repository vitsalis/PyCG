
def f(): pass
def g(): pass
def h(): pass

import ext
mode = "fast"
if mode == "slow":
    f()
elif mode in ("fast", "quick") and mode is not None:
    g()
else:
    h()
level = 2 if ext.flag else 3
if level > 1:
    g()
else:
    f()
if level == 2:
    h()
if mode < 1:
    h()
