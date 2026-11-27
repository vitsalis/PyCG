
def f(): pass
def g(): pass
table = {'pre_65': f, "zz_other": g}
table['pre_%s' % (65,)]()
