import random
import re
import sys

SEED = 20261124
EXPLICIT = 45
IMPLICIT_OTHER = 15
IMPLICIT_GETATTR = 10

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
getattrs = [s for s in numbered if s["kind"] == "getattr"]
other = [s for s in numbered
         if s["kind"] not in ("call", "decorator", "getattr")]

rng = random.Random(SEED)
drawn = (rng.sample(explicit, EXPLICIT) + rng.sample(other, IMPLICIT_OTHER)
         + rng.sample(getattrs, IMPLICIT_GETATTR))
drawn_ids = {s["n"] for s in drawn}
added = [s for s in numbered if s["value"] and s["n"] not in drawn_ids]
sample = sorted(drawn + added, key=lambda s: s["n"])

print(f"# {len(numbered)} sites: {len(explicit)} explicit, {len(getattrs)} "
      f"getattr, {len(other)} other implicit, "
      f"{sum(s['value'] for s in numbered)} value sites")
print(f"# random.Random({SEED}); rng.sample: {EXPLICIT} explicit, then "
      f"{IMPLICIT_OTHER} other implicit, then {IMPLICIT_GETATTR} getattr; "
      f"{len(added)} value sites added; {len(sample)} sites")
for s in sample:
    tag = "drawn" if s["n"] in drawn_ids else "value"
    tag += ",value" if s["value"] and tag == "drawn" else ""
    print(f"{s['n']:4d} {tag:11s} {s['module']} [{s['node']}] "
          f"{s['line']}:{s['col']} {s['kind']}  {s['text']}")
