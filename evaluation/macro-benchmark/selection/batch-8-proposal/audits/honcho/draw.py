import random
import re
import sys

SEED = 20261124
IMPLICIT_ALL_BELOW = 20
SAMPLE = 70

skeleton = open(sys.argv[1]).read().splitlines()
site_re = re.compile(r"^(\d+):(\d+) (\S+)  (.*)$")

modules = []
sites = {}
module = node = None
current = None
for line in skeleton:
    if line.startswith("== "):
        module = line[3:].strip()
        modules.append(module)
        sites[module] = []
    elif line.startswith("["):
        node = line.strip()[1:-1]
    else:
        m = site_re.match(line)
        if m:
            current = {"module": module, "node": node, "line": int(m[1]),
                       "col": int(m[2]), "kind": m[3], "text": m[4],
                       "value": False}
            sites[module].append(current)
        elif line.strip().startswith("# a value site"):
            current["value"] = True

numbered = []
for module in modules:
    numbered.extend(sorted(sites[module], key=lambda s: (s["line"], s["col"])))
for i, s in enumerate(numbered, 1):
    s["n"] = i

explicit = [s for s in numbered if s["kind"] in ("call", "decorator")]
implicit = [s for s in numbered if s["kind"] not in ("call", "decorator")]
assert len(implicit) < IMPLICIT_ALL_BELOW

rng = random.Random(SEED)
drawn = list(implicit) + rng.sample(explicit, SAMPLE - len(implicit))
drawn_ids = {s["n"] for s in drawn}
added = [s for s in numbered if s["value"] and s["n"] not in drawn_ids]
sample = sorted(drawn + added, key=lambda s: s["n"])

print(f"# {len(numbered)} sites: {len(explicit)} explicit, {len(implicit)} implicit, "
      f"{sum(s['value'] for s in numbered)} value sites")
print(f"# random.Random({SEED}); all {len(implicit)} implicit sites, "
      f"{SAMPLE - len(implicit)} explicit drawn with rng.sample; "
      f"{len(added)} value sites added; {len(sample)} sites")
for s in sample:
    tag = "drawn" if s["n"] in drawn_ids else "value"
    tag += ",value" if s["value"] and tag == "drawn" else ""
    print(f"{s['n']:4d} {tag:11s} {s['module']} [{s['node']}] "
          f"{s['line']}:{s['col']} {s['kind']}  {s['text']}")
