def f0(): pass
def f1(): pass
def f2(): pass
def f3(): pass
def f4(): pass
def f5(): pass
def f6(): pass
def f7(): pass
def f8(): pass
def f9(): pass
def f10(): pass
def f11(): pass
def f12(): pass
def f13(): pass

def run(value):
    if f0():
        f1()
    elif f2():
        pass
    else:
        f3()
    for i in f4():
        f5()
    while f6():
        break
    try:
        f7()
    except f8() as error:
        pass
    finally:
        f9()
    with f10() as handle:
        pass
    match value:
        case [first] if f11():
            f12()
    assert f13(), f"{f0()}"
