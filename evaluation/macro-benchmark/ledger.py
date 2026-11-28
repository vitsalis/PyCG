import re
from typing import NamedTuple

_MODULE = re.compile(r"==\s+(\S+)$")
_SCOPE = re.compile(r"\[(\S+)\]$")
_SITE = re.compile(r"(\d+):(\d+)\s+(\S+)(?:\s+(.*))?$")
_REJECT = re.compile(r"reject\s+(.+?):\s+(.+)$")
_EXCLUDE = re.compile(r"exclude\s+(.+?):\s+(.+)$")


class Ledger(NamedTuple):
    entries: list
    default_rejections: dict


class Entry(NamedTuple):
    ledger_line: int
    module: str
    scope: str
    line: int
    column: int
    kind: str
    text: str
    callees: list
    rejected: dict
    excluded: dict
    undecided: list
    notes: list

    @property
    def key(self):
        return (self.module, self.line, self.column, self.kind)


def parse(text):
    entries, defaults, errors = [], {}, []
    module = scope = entry = None
    seen_scopes = set()
    for ledger_line, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "default" or line.startswith("default "):
            problems = _add_default_rejection(defaults, line, ledger_line, module)
            errors += [f"line {ledger_line}: {problem}" for problem in problems]
        elif match := _MODULE.match(line):
            module, scope, entry = match[1], None, None
        elif match := _SCOPE.match(line):
            scope, entry = match[1], None
            if module is None:
                errors.append(f"line {ledger_line}: a node before the first module")
            elif (module, scope) in seen_scopes:
                errors.append(
                    f"line {ledger_line}: [{scope}] appears twice in {module}"
                )
            seen_scopes.add((module, scope))
        elif match := _SITE.match(line):
            if scope is None:
                errors.append(f"line {ledger_line}: a site before the first node")
                continue
            entry = Entry(
                ledger_line=ledger_line,
                module=module,
                scope=scope,
                line=int(match[1]),
                column=int(match[2]),
                kind=match[3],
                text=match[4] or "",
                callees=[],
                rejected={},
                excluded={},
                undecided=[],
                notes=[],
            )
            entries.append(entry)
        elif entry is None:
            errors.append(f"line {ledger_line}: not a module, node or site: {line}")
        else:
            error = _add_item(entry, line)
            if error:
                errors.append(f"line {ledger_line}: {error}")
    return Ledger(entries, defaults), errors


def _add_default_rejection(defaults, line, ledger_line, module):
    if module is not None:
        return ["a default rejection must come before the first module"]
    match = _REJECT.match(line.removeprefix("default").strip())
    if match is None:
        return ["a rejection needs names, a colon and a reason"]
    problems = []
    for name in (n.strip() for n in match[1].split(",")):
        if name == "*":
            problems.append("a default rejection names candidates, not *")
        elif name in defaults:
            problems.append(f"{name} is rejected by default twice")
        else:
            defaults[name] = (match[2], ledger_line)
    return problems


def _add_item(entry, line):
    if line.startswith("->"):
        entry.callees.append(line[2:].strip())
    elif line.startswith("note:"):
        note = line[5:].strip()
        if not note:
            return "an empty note"
        entry.notes.append(note)
    elif line == "undecided" or line.startswith("undecided "):
        entry.undecided.append(line[9:].strip())
    elif match := _REJECT.match(line):
        for name in (n.strip() for n in match[1].split(",")):
            if name in entry.rejected:
                return f"{name} is rejected twice"
            entry.rejected[name] = match[2]
    elif line.startswith("reject"):
        return "a rejection needs names, a colon and a reason"
    elif match := _EXCLUDE.match(line):
        for name in (n.strip() for n in match[1].split(",")):
            if name in entry.excluded:
                return f"{name} is excluded twice"
            entry.excluded[name] = match[2]
    elif line.startswith("exclude"):
        return "an exclusion needs names, a colon and a reason"
    else:
        return f"not an item: {line}"
    return None


def check(ledger, source, packages):
    sites = {site.key: site for site in source.sites}
    defaults = ledger.default_rejections
    errors, seen = [], set()
    for entry in ledger.entries:
        where = f"line {entry.ledger_line}: {entry.line}:{entry.column} {entry.kind}"
        site = sites.get(entry.key)
        if entry.key in seen:
            errors.append(f"{where}: a second entry for the site")
            continue
        seen.add(entry.key)
        if site is None:
            errors.append(f"{where}: no such site in {entry.module} (stale position?)")
            continue
        if site.scope != entry.scope:
            errors.append(f"{where}: the site belongs to [{site.scope}]")
        if site.text != entry.text:
            errors.append(f"{where}: the text of the site is: {site.text}")
        nodes = source.modules | source.functions
        problems = _decisions(entry, site, packages, defaults, nodes)
        errors += [f"{where}: {problem}" for problem in problems]
    for key, site in sites.items():
        if _needs_entry(site, defaults) and key not in seen:
            errors.append(
                f"no entry for {_site_location(site)} in [{site.scope}]: {site.text}"
            )
    for name, decided in coverage(ledger, source).items():
        if not decided:
            ledger_line = defaults[name][1]
            errors.append(f"line {ledger_line}: default reject {name} decides no site")
    return errors


def _needs_entry(site, defaults):
    return site.explicit or bool(site.candidates - defaults.keys())


def coverage(ledger, source):
    entries = {entry.key: entry for entry in ledger.entries}
    decided = {name: [] for name in ledger.default_rejections}
    for site in source.sites:
        entry = entries.get(site.key)
        for name in sorted(site.candidates & decided.keys()):
            if entry is None or not (
                name in entry.callees or name in entry.rejected or "*" in entry.rejected
            ):
                decided[name].append(site)
    return decided


def _decisions(entry, site, packages, defaults, nodes):
    problems = []
    callees = set(entry.callees)
    if entry.undecided:
        names = ", ".join(n or "callees" for n in entry.undecided)
        problems.append(f"undecided: {names}")
    for name in sorted(set(entry.rejected) - site.candidates - {"*"}):
        problems.append(f"{name} is rejected but is not a candidate")
    for name in sorted(callees & set(entry.rejected)):
        problems.append(f"{name} is both a callee and rejected")
    if "*" not in entry.rejected:
        open_ = site.candidates - callees - set(entry.rejected) - defaults.keys()
        for name in sorted(open_):
            if name not in entry.undecided:
                problems.append(f"candidate {name} is neither a callee nor rejected")
    for name in sorted(entry.excluded):
        if name in site.candidates:
            problems.append(f"{name} is a candidate: reject it")
        elif name in callees:
            problems.append(f"{name} is both a callee and excluded")
        elif name not in nodes:
            problems.append(f"{name} is excluded but is not a node of the source")
    if site.value and not entry.notes:
        problems.append("a value site: a note must say where the callee comes from")
    if site.explicit and not callees and not entry.notes:
        problems.append("no callees: write them, or a note on why there are none")
    if not site.explicit:
        for name in sorted(callees):
            if not in_package(name, packages):
                problems.append(
                    f"{name}: an implicit site calls only package functions"
                )
    return problems


def _site_location(site):
    return f"{site.module} {site.line}:{site.column} {site.kind}"


def _site_line(site):
    return f"{site.line}:{site.column} {site.kind}  {site.text}".rstrip()


def in_package(name, packages):
    return any(name == p or name.startswith(p + ".") for p in packages)


def graph(ledger, source):
    result = {node: set() for node in source.modules | source.functions}
    for entry in ledger.entries:
        result.setdefault(entry.scope, set()).update(entry.callees)
    return {node: sorted(result[node]) for node in sorted(result)}


def skeleton(source, title, defaults=None, header=None):
    defaults = defaults or {}
    if header is None:
        header = [
            f"# Call-site ledger of {title}.",
            "# Decide every `undecided` line; see evaluation/benchmark-rules.md.",
        ]
    lines = list(header)
    by_scope = {}
    for site in source.sites:
        if _needs_entry(site, defaults):
            by_scope.setdefault((site.module, site.scope), []).append(site)
    module = None
    for key in source.scopes:
        if key not in by_scope:
            continue
        if key[0] != module:
            module = key[0]
            lines += ["", f"== {module}"]
        lines += ["", f"[{key[1]}]"]
        for site in by_scope[key]:
            lines.append(_site_line(site))
            if site.value:
                lines.append("    # a value site: note where the callee comes from")
            if site.explicit:
                lines.append("    undecided")
            open_ = site.candidates - defaults.keys()
            lines += [f"    undecided {name}" for name in sorted(open_)]
    return "\n".join(lines) + "\n"


def report(ledger, source, missing_edges, listed=None, without_candidates=False):
    sites = {site.key: site for site in source.sites}
    undecided, values, beyond = [], [], []
    for entry in ledger.entries:
        site = sites.get(entry.key)
        if site is None:
            continue
        label = f"{_site_location(site)} [{site.scope}] {site.text}"
        if entry.undecided:
            undecided.append(
                f"{label}: {', '.join(n or 'callees' for n in entry.undecided)}"
            )
        if site.value:
            values.append(label)
            values += [f"    note: {note}" for note in entry.notes]
            values += [f"    -> {callee}" for callee in entry.callees]
            values += [f"    exclude {n}: {r}" for n, r in entry.excluded.items()]
        else:
            extra = sorted(
                c for c in set(entry.callees) - site.candidates if c in source.functions
            )
            if extra:
                beyond.append(f"{label}: -> {', '.join(extra)}")
    defaults = []
    for name, decided in coverage(ledger, source).items():
        reason = ledger.default_rejections[name][0]
        defaults.append(f"{name}: {len(decided)} sites: {reason}")
        for site in decided:
            line = f"{site.module} [{site.scope}] {_site_line(site)}"
            if name == listed:
                defaults.append(f"    {line}")
            elif site.explicit:
                defaults.append(f"    explicit: {line}")
    sections = [
        ("sites with undecided candidates or callees", undecided),
        ("value sites", values),
        ("sites with package callees that are not candidates", beyond),
        ("default rejections", defaults),
        ("trace edges that no site of the caller accounts for", missing_edges),
    ]
    if without_candidates:
        bare = [
            f"{site.module} [{site.scope}] {_site_line(site)}"
            for site in source.sites
            if not site.needs_entry
        ]
        sections.append(("implicit sites without candidates", bare))
    lines = []
    for title, items in sections:
        count = sum(not item.startswith("    ") for item in items)
        lines.append(f"{title}: {count}")
        lines += [f"  {item}" for item in items]
    return lines
