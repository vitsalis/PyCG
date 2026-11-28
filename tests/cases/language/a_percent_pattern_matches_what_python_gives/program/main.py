
def f(): pass
def g(): pass
table = {'65': f, "zz_other": g}
table['%s' % (65,)]()
