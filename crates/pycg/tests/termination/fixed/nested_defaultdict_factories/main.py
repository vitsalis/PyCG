from collections import defaultdict
d = defaultdict(lambda: defaultdict(list))
for _ in range(2):
    d = d[0]
    d = d.copy()
