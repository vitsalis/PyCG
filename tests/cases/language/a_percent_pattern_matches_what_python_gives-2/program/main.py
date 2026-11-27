
def f(): pass
def g(): pass
table = {'_tail65': f, "zz_other": g}
table['_tail%s' % (65,)]()
