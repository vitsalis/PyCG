def evens():
    return [2, 4]

def odds():
    return [1, 3]

def defaults():
    return {"a": 1}

numbers = [*source() for source in (evens, odds)]
settings = {**make() for make in (defaults,)}
