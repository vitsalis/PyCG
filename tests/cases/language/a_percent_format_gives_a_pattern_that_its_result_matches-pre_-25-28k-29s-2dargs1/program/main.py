
def f(): pass
def g(): pass
table = {'pre_v': f, "zz_other": g}
table['pre_%(k)s' % {'k': 'v'}]()
