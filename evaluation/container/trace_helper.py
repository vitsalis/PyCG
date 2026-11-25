#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
ROUND_LOGS = REPOSITORY / "evaluation" / "macro-benchmark" / "selection"
TRACE_SIZE_BYTES_MAX = 64 * 1024 * 1024
PYTHON_IMAGE_PATTERN = re.compile(r"[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}")
OUTCOMES = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
TRACE_TYPE_BY_KEY = {
    "aliases": dict,
    "commit": str,
    "deselect": list,
    "distributions": dict,
    "dropped": dict,
    "edges": dict,
    "executed": list,
    "functions": list,
    "modules": list,
    "project": str,
    "pytest": dict,
    "python": str,
    "tests": dict,
}
TRACE_OPTIONAL_TYPE_BY_KEY = {"plugins": list, "environment": dict, "failures": dict}
USAGE = """usage:
    trace_helper.py check-pin BENCHMARK_DIR NAME
    trace_helper.py plugins BENCHMARK_DIR NAME
    trace_helper.py image-tag NAME DOCKERFILE REQUIREMENTS PYTHON_IMAGE
    trace_helper.py check-trace TRACE BENCHMARK_DIR NAME PYTHON_IMAGE
    trace_helper.py compare COMMITTED_TRACE NEW_TRACE

The checks of container/trace.sh (evaluation/macro-benchmark/README.md,
"Recording traces in a container")."""


class HelperError(Exception):
    pass


def _projects():
    path = REPOSITORY / "evaluation" / "macro-benchmark" / "projects.py"
    spec = importlib.util.spec_from_file_location("macro_projects", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_projects():
    return _projects().load_projects


def project(benchmark_dir, name):
    projects = _load_projects()(Path(benchmark_dir) / "projects.toml")
    if name not in projects:
        raise HelperError(f"{name} is not a project of {benchmark_dir}/projects.toml")
    if projects[name].pin is None:
        raise HelperError(f"{name} has neither a commit nor an sdist in projects.toml")
    return projects[name]


def round_log_selection_by_name(logs=ROUND_LOGS):
    found = {}
    for path in sorted(Path(logs).glob("round-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for stratum in data.get("strata", []):
            selected = stratum.get("selected")
            if selected:
                found[selected["name"]] = (selected["facts"], path.name)
    return found


def commit_checked_against_round_log(benchmark_dir, name, logs=ROUND_LOGS):
    pinned = project(benchmark_dir, name).commit
    if pinned is None:
        raise HelperError(f"{name} has no commit in projects.toml: it names an sdist")
    drawn = round_log_selection_by_name(logs).get(name)
    if drawn is not None and drawn[0]["commit"] != pinned:
        raise HelperError(
            f"projects.toml pins {name} at {pinned}, {drawn[1]} at {drawn[0]['commit']}"
        )
    return pinned


def sdist_checked_against_round_log(benchmark_dir, name, logs=ROUND_LOGS):
    archive = project(benchmark_dir, name).sdist
    if archive is None:
        return None
    drawn = round_log_selection_by_name(logs).get(name)
    if drawn is not None:
        release = drawn[0]["release"]
        wanted = f"{re.sub(r'[-_.]+', '_', name).lower()}-{release}.tar.gz"
        if archive.file != wanted:
            raise HelperError(
                f"projects.toml names {archive.file} for {name}, "
                f"{drawn[1]} draws release {release} ({wanted})"
            )
    return archive.file


def check_pin(benchmark_dir, name, logs=ROUND_LOGS):
    item = project(benchmark_dir, name)
    if item.sdist is None:
        commit_checked_against_round_log(benchmark_dir, name, logs)
    else:
        sdist_checked_against_round_log(benchmark_dir, name, logs)
    kind = "commit" if item.sdist is None else "sdist"
    return f"{kind} of the round log: {name} at {item.pin}"


def plugins(benchmark_dir, name):
    benchmark = Path(benchmark_dir).resolve()
    return [
        p.relative_to(benchmark).as_posix() for p in project(benchmark, name).plugins
    ]


def image_tag(name, dockerfile, requirements, python_image):
    if not PYTHON_IMAGE_PATTERN.fullmatch(python_image):
        raise HelperError(f"PYTHON_IMAGE {python_image!r} is not NAME@sha256:<digest>")
    digest = hashlib.sha256()
    digest.update(Path(dockerfile).read_bytes())
    digest.update(Path(requirements).read_bytes())
    digest.update(python_image.encode())
    return f"pycg-trace-{name.lower()}:{digest.hexdigest()[:12]}"


def requirement_by_normalized_name(path):
    text = Path(path).read_text(encoding="utf-8").replace("\\\n", " ")
    found = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9._-]+)==(\S+)\s", line + " ")
        if match is None or "--hash=sha256:" not in line:
            raise HelperError(f"{path}: not name==version with hashes: {line!r}")
        found[_normalize(match[1])] = (match[1], match[2])
    return found


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _check_shape(data, name, pinned, environment=None):
    problems = []
    if not isinstance(data, dict):
        return ["the trace is not a JSON object"]
    extra = data.keys() - TRACE_TYPE_BY_KEY.keys() - TRACE_OPTIONAL_TYPE_BY_KEY.keys()
    missing = TRACE_TYPE_BY_KEY.keys() - data.keys()
    problems += [f"unexpected key {k!r}" for k in sorted(extra)]
    problems += [f"missing key {k!r}" for k in sorted(missing)]
    for key, kind in {**TRACE_TYPE_BY_KEY, **TRACE_OPTIONAL_TYPE_BY_KEY}.items():
        if key in data and not isinstance(data[key], kind):
            problems.append(f"{key!r} is not a {kind.__name__}")
    if problems:
        return problems
    for key in ("edges", "aliases"):
        if not all(
            isinstance(k, str)
            and isinstance(v, list)
            and all(isinstance(x, str) for x in v)
            for k, v in data[key].items()
        ):
            problems.append(f"{key!r} is not a mapping of names to lists of names")
    for key in ("modules", "functions", "executed", "plugins"):
        if not all(isinstance(x, str) for x in data.get(key, [])):
            problems.append(f"{key!r} is not a list of names")
    failures = data.get("failures", {"errors": [], "failed": []})
    if set(failures) != {"errors", "failed"} or not all(
        isinstance(ids, list) and all(isinstance(i, str) for i in ids)
        for ids in failures.values()
    ):
        problems.append("'failures' is not the lists of failed and errored test ids")
    recorded = data.get("environment", {})
    if not all(isinstance(v, str) for v in recorded.values()):
        problems.append("'environment' is not a mapping of names to strings")
    elif recorded != (environment or {}):
        problems.append(
            f"the trace has the environment {recorded}, its entry {environment or {}}"
        )
    counts = [data["tests"].get(k) for k in (*OUTCOMES, "deselected")]
    if not all(isinstance(c, int) for c in counts):
        problems.append("'tests' has no count for each outcome")
    if data["tests"].get("exit_status") not in (0, 1):
        problems.append(f"pytest exit status {data['tests'].get('exit_status')}")
    if data["project"] != name:
        problems.append(f"the trace is of {data['project']!r}, not {name!r}")
    if data["commit"] != pinned:
        problems.append(f"the trace is of commit {data['commit']}, not {pinned}")
    return problems


def check_trace(trace_path, benchmark_dir, name, python_image, destination=None):
    benchmark = Path(benchmark_dir)
    entry = project(benchmark, name)
    pinned = entry.pin
    info = os.lstat(trace_path)
    if not stat.S_ISREG(info.st_mode):
        raise HelperError(f"{trace_path} is not a regular file")
    if info.st_size > TRACE_SIZE_BYTES_MAX:
        raise HelperError(f"{trace_path} has {info.st_size} bytes, over the limit")
    text = Path(trace_path).read_text(encoding="utf-8")
    data = json.loads(text)
    problems = _check_shape(data, name, pinned, dict(entry.environment))
    if not problems and json.dumps(data, indent=2, sort_keys=True) + "\n" != text:
        problems.append("the trace is not in the format that trace.py writes")
    wanted = requirement_by_normalized_name(
        benchmark / "test-environments" / f"{name}.txt"
    )
    if not problems:
        installed = {_normalize(n): (n, v) for n, v in data["distributions"].items()}
        for key in sorted(wanted.keys() | installed.keys()):
            if key not in installed:
                problems.append(f"{wanted[key][0]} is not installed in the container")
            elif key not in wanted:
                problems.append(f"{installed[key][0]} is installed, not required")
            elif installed[key][1] != wanted[key][1]:
                problems.append(
                    f"{installed[key][0]} {installed[key][1]} is installed, "
                    f"the requirements pin {wanted[key][1]}"
                )
    if problems:
        raise HelperError("\n".join(problems))
    directory = Path(destination) if destination else None
    destination = (directory or benchmark / "dynamic") / f"{name}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    lines = [
        f"# The distributions in the container of the trace of {name}",
        f"# (dynamic/{name}.json), on CPython {data['python']}; the image was",
        f"# built from {python_image}.",
        *(
            f"{n}=={v}"
            for n, v in sorted(
                data["distributions"].items(), key=lambda i: _normalize(i[0])
            )
        ),
    ]
    installed_path = (directory or benchmark / "test-environments") / (
        f"{name}.installed.txt"
    )
    installed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tests = ", ".join(f"{data['tests'][o]} {o}" for o in (*OUTCOMES, "deselected"))
    edges = sum(len(callees) for callees in data["edges"].values())
    return (
        f"{name}: {edges} edges, {len(data['executed'])} functions run; "
        f"tests: {tests}; wrote {destination} and {installed_path}"
    )


CALLEE_KINDS = ("package", "builtin", "library")


def _read_trace(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(data.get(k), TRACE_TYPE_BY_KEY[k])
        for k in ("edges", "tests", "modules")
    ):
        raise HelperError(f"{path} is not a trace")
    return data


def _test_counts(data):
    counts = [
        f"{data['tests'].get(o, 0)} {o}"
        for o in (*OUTCOMES, "deselected")
        if data["tests"].get(o, 0)
    ]
    return ", ".join(counts) or "no tests"


def _longest_package_module_containing(name, modules):
    found = [m for m in modules if name == m or name.startswith(m + ".")]
    return max(found, key=len) if found else name


def _callee_kind(callee, modules):
    if callee.startswith("<builtin>."):
        return "builtin"
    if any(callee.startswith(m + ".") for m in modules):
        return "package"
    return "library"


def compare(committed_path, new_path):
    traces = {"committed": _read_trace(committed_path), "new": _read_trace(new_path)}
    old, new = traces["committed"], traces["new"]
    modules = set(old["modules"]) | set(new["modules"])
    edges = {
        side: {(a, b) for a, callees in data["edges"].items() for b in callees}
        for side, data in traces.items()
    }
    width = max(20, len(old.get("python", "")), len(_test_counts(old))) + 2
    lines = [
        f"{'':<16}{'committed':<{width}}new",
        f"{'python':<16}{old.get('python', '-'):<{width}}{new.get('python', '-')}",
        f"{'tests':<16}{_test_counts(old):<{width}}{_test_counts(new)}",
        f"{'edges':<16}{len(edges['committed']):<{width}}{len(edges['new'])}",
    ]
    names = {}
    for side, data in traces.items():
        for name, version in data.get("distributions", {}).items():
            names.setdefault(_normalize(name), {"name": name})[side] = version
    differ = [v for _, v in sorted(names.items()) if v.get("committed") != v.get("new")]
    if differ:
        lines.append("distributions that differ:")
        lines += [
            f"  {v['name']:<14}{v.get('committed', '-'):<{width}}{v.get('new', '-')}"
            for v in differ
        ]
    lines.append(f"edges in both: {len(edges['committed'] & edges['new'])}")
    for side, other in (("committed", "new"), ("new", "committed")):
        only = edges[side] - edges[other]
        if not only:
            continue
        lines.append(f"only in the {side} trace: {len(only)}")
        grouped = {}
        for caller, callee in only:
            kind = _callee_kind(callee, modules)
            module = _longest_package_module_containing(caller, modules)
            grouped.setdefault(module, []).append((caller, callee, kind))
        column = max(len(m) for m in grouped) + 2
        lines.append(f"  {'caller module':<{column}}" + " ".join(CALLEE_KINDS))
        for module, found in sorted(grouped.items()):
            counts = [sum(k == kind for *_, k in found) for kind in CALLEE_KINDS]
            row = " ".join(f"{c:<{len(k)}}" for c, k in zip(counts, CALLEE_KINDS))
            lines.append(f"  {module:<{column}}{row}".rstrip())
        for module, found in sorted(grouped.items()):
            lines.append(f"  {module}:")
            lines += [f"    {a} -> {b}  [{k}]" for a, b, k in sorted(found)]
    equal = edges["committed"] == edges["new"]
    lines.append(
        f"the edge sets are equal ({len(edges['new'])} edges)"
        if equal
        else "the edge sets differ"
    )
    return lines, equal


def main(argv):
    command, args = argv[0] if argv else None, argv[1:]
    try:
        if command == "check-pin" and len(args) == 2:
            print(check_pin(*args))
        elif command == "plugins" and len(args) == 2:
            for path in plugins(*args):
                print(path)
        elif command == "image-tag" and len(args) == 4:
            print(image_tag(*args))
        elif command == "check-trace" and len(args) == 4:
            print(check_trace(*args))
        elif command == "compare" and len(args) == 2:
            lines, equal = compare(*args)
            print("\n".join(lines))
            return 0 if equal else 1
        else:
            print(USAGE, file=sys.stderr)
            return 2
    except (HelperError, ValueError, OSError) as exc:
        print(f"trace_helper.py {command}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
