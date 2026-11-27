from collections import defaultdict
def build(factory):
    return defaultdict(factory)
d = build(list)
d = build(d.copy)
for _ in range(2):
    d = d[0]
