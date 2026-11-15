MISSING = sentinel("MISSING")

def compute():
    return 1

def get(value=MISSING):
    if value is MISSING:
        value = compute()
    return value

get()
