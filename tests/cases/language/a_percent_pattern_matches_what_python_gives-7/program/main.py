
def f(): pass
def g(): pass
table = {'a65': f, "zz_other": g}
table['a%-s' % (65,)]()
