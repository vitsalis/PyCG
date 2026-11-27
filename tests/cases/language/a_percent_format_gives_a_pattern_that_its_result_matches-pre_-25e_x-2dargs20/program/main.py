
def f(): pass
def g(): pass
table = {'pre_6.500000e+01_x': f, "zz_other": g}
table['pre_%e_x' % (65,)]()
