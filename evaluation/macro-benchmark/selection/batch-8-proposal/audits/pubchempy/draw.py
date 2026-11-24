import random
import re
import sys

SITE = re.compile(r"^(\d+):(\d+) (\S+)  (.*)$")
EXPLICIT = {"call", "decorator"}
VALUE_SITES = [
    (803, 6), (806, 42), (816, 10), (823, 24),
    (1099, 19), (1742, 19), (1923, 19), (2112, 23),
]


def sites(path):
    module = None
    found = []
    for line in open(path):
        if line.startswith("== "):
            module = line[3:].strip()
            continue
        m = SITE.match(line.rstrip("\n"))
        if m:
            found.append((module, int(m[1]), int(m[2]), m[3], m[4]))
    return found


def main(skeleton):
    numbered = sorted(sites(skeleton), key=lambda s: (s[1], s[2]))
    explicit = [s for s in numbered if s[3] in EXPLICIT]
    implicit = [s for s in numbered if s[3] not in EXPLICIT]
    rng = random.Random(20261124)
    drawn = rng.sample(explicit, 90) + rng.sample(implicit, 50)
    keys = {(s[1], s[2]) for s in drawn}
    added = [s for s in numbered if (s[1], s[2]) in VALUE_SITES and (s[1], s[2]) not in keys]
    print(f"# skeleton sites {len(numbered)}: explicit {len(explicit)}, implicit {len(implicit)}")
    print(f"# drawn 90 explicit + 50 implicit; value sites added: {len(added)}")
    for group, rows in (("explicit", drawn[:90]), ("implicit", drawn[90:]), ("value", added)):
        for s in sorted(rows, key=lambda s: (s[1], s[2])):
            print(f"{group}\t{s[0]}\t{s[1]}:{s[2]}\t{s[3]}\t{s[4]}")


main(sys.argv[1])
