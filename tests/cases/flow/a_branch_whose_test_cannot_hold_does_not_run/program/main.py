
def f(): pass
def g(): pass
def h(): pass

import ext
if False:
    f()
while 0:
    f()
if ():
    f()
elif ext.flag:
    g()
else:
    h()
fast = True
if fast:
    def handler():
        g()
else:
    def handler():
        f()
handler()
if not fast:
    def unused():
        pass
