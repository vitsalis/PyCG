
def f(): pass
def g(): pass
table = {'6': f, "zz_other": g}
table['%(k) .1s' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
