def positive():
    pass

def negative():
    pass

for value in (1, -1):
    match value:
        case +1:
            positive()
        case -1:
            negative()
