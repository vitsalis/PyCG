
def f(): pass
def g(): pass
table = {'pre_6.500000E+01_x': f, "zz_other": g}
table['pre_%E_x' % (65,)]()
