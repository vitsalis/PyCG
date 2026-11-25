def average(values):
    return sum(values) / len(values)

def to_gray(r, g, b):
    return average([r, g, b])
