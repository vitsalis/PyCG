"""The call-site ledger: the hand-written ground truth of a macro-benchmark project.

The ledger has one entry per call site (see sites.py) and states its
callees. The adjacency list ground-truth/<name>.json is generated from it.
The format (see evaluation/macro-benchmark/README.md):

    # A comment.
    default reject a.f: reason              rejects a.f wherever no entry decides it
    == jmespath.parser                      the module (file) of the sites below
    [jmespath.parser.Parser.parse]          the node that the calls belong to
    102:31 call  self._parse(expression)    line:column kind text
        -> jmespath.parser.Parser._parse    a callee
        reject a.f, b.f: reason             rejected candidates
        reject *: reason                    every other candidate
        exclude a.g: reason                 a node considered, not a candidate
        undecided a.f                       a candidate to decide (skeleton)
        undecided                           callees to write (skeleton)
        note: where the callee comes from
"""

import re
from typing import NamedTuple

_MODULE = re.compile(r"==\s+(\S+)$")
_SCOPE = re.compile(r"\[(\S+)\]$")
_SITE = re.compile(r"(\d+):(\d+)\s+(\S+)(?:\s+(.*))?$")
_REJECT = re.compile(r"reject\s+(.+?):\s+(.+)$")
_EXCLUDE = re.compile(r"exclude\s+(.+?):\s+(.+)$")


class Ledger(NamedTuple):
    entries: list
    defaults: dict  # candidate -> (reason, line of the ledger)


class Entry(NamedTuple):
    """The ledger entry of one call site."""

    at: int  # line of the ledger
    module: str
    scope: str
    line: int
    column: int
    kind: str
    text: str
    callees: list
    rejected: dict  # candidate -> reason; "*" for every other candidate
    excluded: dict  # node that is not a candidate -> reason
    undecided: list  # candidates; "" for the callees of the site
    notes: list

    @property
    def key(self):
        return (self.module, self.line, self.column, self.kind)


def parse(text):
    """Return (ledger, errors) for the text of a ledger."""
    entries, defaults, errors = [], {}, []
    module = scope = entry = None
    seen_scopes = set()
    for at, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "default" or line.startswith("default "):
            problems = _default(defaults, line, at, module)
            errors += [f"line {at}: {problem}" for problem in problems]
        elif match := _MODULE.match(line):
            module, scope, entry = match[1], None, None
        elif match := _SCOPE.match(line):
            scope, entry = match[1], None
            if module is None:
                errors.append(f"line {at}: a node before the first module")
            elif (module, scope) in seen_scopes:
                errors.append(f"line {at}: [{scope}] appears twice in {module}")
            seen_scopes.add((module, scope))
        elif match := _SITE.match(line):
            if scope is None:
                errors.append(f"line {at}: a site before the first node")
                continue
            entry = Entry(
                at=at,
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
            errors.append(f"line {at}: not a module, node or site: {line}")
        else:
            error = _item(entry, line)
            if error:
                errors.append(f"line {at}: {error}")
    return Ledger(entries, defaults), errors


def _default(defaults, line, at, module):
    """Add a default rejection to `defaults`; return the problems."""
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
            defaults[name] = (match[2], at)
    return problems


def _item(entry, line):
    """Add an item line to `entry`; return an error message or None."""
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
    """List the problems of a ledger against the sites of the source."""
    sites = {site.key: site for site in source.sites}
    defaults = ledger.defaults
    errors, seen = [], set()
    for entry in ledger.entries:
        where = f"line {entry.at}: {entry.line}:{entry.column} {entry.kind}"
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
            errors.append(f"no entry for {_where(site)} in [{site.scope}]: {site.text}")
    for name, decided in coverage(ledger, source).items():
        if not decided:
            at = defaults[name][1]
            errors.append(f"line {at}: default reject {name} decides no site")
    return errors


def _needs_entry(site, defaults):
    """Whether a site needs an entry: what defaults leave of it to decide."""
    return site.explicit or bool(site.candidates - defaults.keys())


def coverage(ledger, source):
    """{default rejection: the sites where it decides}: where no entry
    accepts or rejects that candidate itself."""
    entries = {entry.key: entry for entry in ledger.entries}
    decided = {name: [] for name in ledger.defaults}
    for site in source.sites:
        entry = entries.get(site.key)
        for name in sorted(site.candidates & decided.keys()):
            if entry is None or not (
                name in entry.callees or name in entry.rejected or "*" in entry.rejected
            ):
                decided[name].append(site)
    return decided


def _decisions(entry, site, packages, defaults, nodes):
    """The problems of the decisions in one entry."""
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


def _where(site):
    return f"{site.module} {site.line}:{site.column} {site.kind}"


def _site_line(site):
    """The line of a site in a ledger."""
    return f"{site.line}:{site.column} {site.kind}  {site.text}".rstrip()


def in_package(name, packages):
    return any(name == p or name.startswith(p + ".") for p in packages)


def graph(ledger, source):
    """The adjacency list: every node, with the callees of its sites."""
    result = {node: set() for node in source.modules | source.functions}
    for entry in ledger.entries:
        result.setdefault(entry.scope, set()).update(entry.callees)
    return {node: sorted(result[node]) for node in sorted(result)}


def skeleton(source, title, defaults=None, header=None):
    """A ledger with every site that needs an entry and its candidates undecided.

    It leaves out what `defaults` (default rejections) decide. `header` is
    the part of an existing ledger before its first module (comments and
    default rejections); it replaces the title.
    """
    defaults = defaults or {}
    if header is None:
        header = [
            f"# Call-site ledger of {title}.",
            "# Decide every `undecided` line; see macro-benchmark/README.md.",
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
            if site.explicit:  # callees outside the package, if any
                lines.append("    undecided")
            open_ = site.candidates - defaults.keys()
            lines += [f"    undecided {name}" for name in sorted(open_)]
    return "\n".join(lines) + "\n"


def report(ledger, source, missing_edges, listed=None, without_candidates=False):
    """The report for auditors: the sites where a missing edge is most likely.

    It also counts the sites that each default rejection decides, with the
    explicit ones (calls and decorators), and lists every site of the default
    rejection of `listed`. With `without_candidates`, it also lists the
    implicit sites without candidates, which the skeleton leaves out.
    """
    sites = {site.key: site for site in source.sites}
    undecided, values, beyond = [], [], []
    for entry in ledger.entries:
        site = sites.get(entry.key)
        if site is None:
            continue
        label = f"{_where(site)} [{site.scope}] {site.text}"
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
        reason = ledger.defaults[name][0]
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
