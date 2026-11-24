values = [3, 2, 1]

def next_value():
    return values.pop()

for value in iter(next_value, 3):
    pass
