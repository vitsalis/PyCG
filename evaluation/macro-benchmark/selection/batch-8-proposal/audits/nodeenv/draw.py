import random
import re
import sys

SITE = re.compile(r"^(\d+):(\d+) (\S+)  (.*)$")


def sites(skeleton, report):
    module = node = None
    found = []
    for line in open(skeleton):
        line = line.rstrip("\n")
        if line.startswith("== "):
            module = line[3:]
        elif line.startswith("["):
            node = line[1:-1]
        else:
            m = SITE.match(line)
            if m:
                found.append((module, int(m[1]), int(m[2]), m[3], node, m[4]))
    order = {}
    for site in found:
        order.setdefault(site[0], len(order))
    found.sort(key=lambda s: (order[s[0]], s[1], s[2]))
    value = set()
    inside = False
    for line in open(report):
        if line.startswith("  value sites:"):
            inside = True
        elif inside and line.startswith("    "):
            module, pos = line.split()[:2]
            line_no, col = pos.split(":")
            value.add((module, int(line_no), int(col)))
        elif inside:
            inside = False
    return found, value


def main():
    skeleton, report = sys.argv[1:3]
    found, value = sites(skeleton, report)
    explicit = [i for i, s in enumerate(found) if s[3] in ("call", "decorator")]
    implicit = [i for i, s in enumerate(found) if s[3] not in ("call", "decorator")]
    assert not implicit
    rng = random.Random(20261124)
    drawn = sorted(rng.sample(explicit, 70))
    added = sorted(i for i, s in enumerate(found) if s[:3] in value and i not in drawn)
    assert len([s for s in found if s[:3] in value]) == len(value)
    print(f"# {len(found)} sites ({len(explicit)} explicit, {len(implicit)} implicit); "
          f"{len(value)} value sites; drawn 70, value sites added {len(added)}")
    for group, ids in (("draw", drawn), ("value", added)):
        for i in ids:
            module, line, col, kind, node, text = found[i]
            mark = " value" if (module, line, col) in value else ""
            print(f"{group} #{i + 1} {module} [{node}] {line}:{col} {kind}{mark}  {text}")


main()
