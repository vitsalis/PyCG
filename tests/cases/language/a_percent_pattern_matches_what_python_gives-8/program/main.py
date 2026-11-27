
def f(): pass
def g(): pass
table = {'pre_   65': f, "zz_other": g}
table['pre_%+5s' % (65,)]()
