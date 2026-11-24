def level3():
    pass

def level2():
    return level3

def level1():
    return level2

level1()()()
