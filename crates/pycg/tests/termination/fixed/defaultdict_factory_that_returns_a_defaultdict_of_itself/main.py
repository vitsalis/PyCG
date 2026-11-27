from collections import defaultdict
def tree():
    return defaultdict(tree)
t = tree()
for _ in range(2):
    t = t['k'].copy()
