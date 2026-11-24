import random
import re
import sys

skeleton = sys.argv[1]
sites = []
module = node = None
value = set()
with open(skeleton) as f:
    for line in f:
        line = line.rstrip("\n")
        if line.startswith("== "):
            module = line[3:]
        elif line.startswith("["):
            node = line
        elif re.match(r"^\d+:\d+ ", line):
            pos, kind = line.split()[:2]
            ln, col = map(int, pos.split(":"))
            sites.append((module, ln, col, kind, node, line))
        elif "a value site" in line:
            value.add(len(sites) - 1)

order = []
for s in sites:
    if s[0] not in order:
        order.append(s[0])
numbered = sorted(range(len(sites)), key=lambda i: (order.index(sites[i][0]), sites[i][1], sites[i][2]))
num = {i: n + 1 for n, i in enumerate(numbered)}

explicit = [num[i] for i in numbered if sites[i][3] in ("call", "decorator")]
getattr_ = [num[i] for i in numbered if sites[i][3] == "getattr"]
other = [num[i] for i in numbered if sites[i][3] not in ("call", "decorator", "getattr")]

rng = random.Random(20261124)
drawn = (
    [("explicit", n) for n in sorted(rng.sample(explicit, 50))]
    + [("getattr", n) for n in sorted(rng.sample(getattr_, 10))]
    + [("implicit", n) for n in sorted(rng.sample(other, 10))]
)
taken = {n for _, n in drawn}
drawn += [("value", num[i]) for i in numbered if i in value and num[i] not in taken]

print(f"# {len(sites)} sites: {len(explicit)} explicit, {len(getattr_)} getattr, {len(other)} other implicit; {len(value)} value sites")
by_num = {num[i]: i for i in numbered}
for group, n in drawn:
    m, ln, col, kind, node, line = sites[by_num[n]]
    tag = " value" if by_num[n] in value else ""
    print(f"{n:5d} {group:9s}{tag:6s} {m} {node} {line}")
