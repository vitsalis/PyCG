"""Choose the packages of a new batch of the macro-benchmark, by a procedure that
another person can run again: a fixed public list at a recorded date, a
quality-filtered frame that is computed once and frozen, and a seeded draw
stratified by size.

    python -I evaluation/macro-benchmark/draw.py frame --work DIR [--offline]
    python -I evaluation/macro-benchmark/draw.py draw --round N
        [--used DIR]... [--drop NAME=REASON]...
    python -I evaluation/macro-benchmark/draw.py check NAME[==VERSION]... --work DIR

`frame` evaluates every package of the list up to RANK_CUTOFF through the
filters (FILTERS, cheap ones first; the first failure ends a package), in
rank order, and writes selection/frame.json: the funnel, and per package
the failed filter and why, or the facts of a pass. The frame does not depend
on the batches already built: packages that are used or excluded are evaluated
like the others and skipped only by the draw.

`draw` reads the frozen frame, never the network. It sorts the passing
packages by code lines (ties by name), cuts them into STRATA equal-count
strata, shuffles their names with a seed derived from the list and the
round, and takes for each stratum the first package of that order that is
in the stratum and is not used, excluded or dropped. It writes
selection/round-<N>.json.

`check` evaluates every filter on named packages, all of them even after a
failure. It writes no frame and no round log, but fills the cache.

The network is the boundary: Internet makes every request, Cache keeps every
response under --work, so that a run resumes where it stopped and a rerun
reads the cache (--offline never fetches); Cache waits when the GitHub API
answers that its limit is reached. A wheel is read as a zip and a clone as
files: nothing of a package is installed, imported or run. Standard library
only (Python 3.12 or later).
"""

import argparse
import datetime
import fnmatch
import hashlib
import http.client
import io
import json
import math
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time
import tokenize
import tomllib
import urllib.error
import urllib.request
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[1]
SELECTION_DIR = HERE / "selection"
LIST_PATH = SELECTION_DIR / "top-pypi-packages-2026-11-01.json"
EXCLUDED_PATH = SELECTION_DIR / "excluded.txt"
FRAME_PATH = SELECTION_DIR / "frame.json"
USED_DIRS = (HERE,)

# The thresholds of the procedure. The frame and the round logs record them.
# frame and check run only on this Python: the code-line count uses the
# tokenizer, whose tokens differ between versions (t-strings since 3.14).
FRAME_PYTHON = (3, 15)
RANK_CUTOFF = 5000  # rank: the frame is the packages of rank 1 to this
STUB_PREFIXES = ("types-",)  # stub-name, on the normalised name
STUB_SUFFIXES = ("-stubs",)
MAINTAINED_YEARS = 3  # release: at most this old at the list date
PURE_WHEEL_TAGS = ("py3-none-any", "py2.py3-none-any")  # pure-python
TARGET_PYTHON = "3.14.0"  # requires-python and no-dependency
MARKER_ENVIRONMENT = {  # no-dependency: CPython 3.14 on Linux, no extra
    "python_version": "3.14",
    "python_full_version": TARGET_PYTHON,
    "sys_platform": "linux",
    "platform_system": "Linux",
    "os_name": "posix",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "extra": "",
}
PERMISSIVE_LICENCES = (  # licence and github: SPDX identifiers
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "PSF-2.0",
    "Unlicense",
)
PERMISSIVE_CLASSIFIERS = (
    "License :: OSI Approved :: Apache Software License",
    "License :: OSI Approved :: BSD License",
    "License :: OSI Approved :: ISC License (ISCL)",
    "License :: OSI Approved :: MIT License",
    "License :: OSI Approved :: Python Software Foundation License",
    "License :: OSI Approved :: The Unlicense (Unlicense)",
    "License :: OSI Approved :: Zero-Clause BSD (0BSD)",
)
MIN_CODE_LINES = 800  # size
MAX_CODE_LINES = 4000
TEST_DIRS = ("tests", "test", "testing", "unittests")  # size: not counted
TAG_FORMS = ("{version}", "v{version}", "{name}-{version}", "release-{version}")
MIN_COMMITS = 100  # history, at the tag
MIN_AUTHORS = 2  # history: distinct author e-mails
CI_FILES = (  # ci: a path ending in / means any file below it
    ".github/workflows/",
    ".travis.yml",
    ".gitlab-ci.yml",
    ".circleci/",
    "azure-pipelines.yml",
)
TEST_FILES = ("test_*.py", "*_test.py")  # tests
MAX_DIFFERING_PERCENT = 5  # released-code
MIN_STARS = 500  # github
MAX_BLOB_BYTES = 4 * 1024 * 1024  # tests and released-code: larger files are not read
STRATA = 5  # draw: one package per stratum
GITHUB_FACTS = (  # recorded as fetched
    "archived",
    "created_at",
    "fork",
    "forks_count",
    "full_name",
    "open_issues_count",
    "pushed_at",
    "stargazers_count",
    "subscribers_count",
)

PYPI_PROJECT = "https://pypi.org/pypi/{name}/json"
PYPI_RELEASE = "https://pypi.org/pypi/{name}/{version}/json"
GITHUB_API = "https://api.github.com/repos/{owner}/{repo}"
HTTP_TIMEOUT = 60
HTTP_ATTEMPTS = 8  # requests for one body, also to continue a cut one
HTTP_PAUSE = 2  # seconds between two of them
USER_AGENT = "pycg-macro-benchmark-draw"


class Offline(Exception):
    """A response that --offline needs is not in the cache."""


class NotEvaluated(Exception):
    """A filter needs a fact that an earlier filter did not find (check)."""


class RateLimited(Exception):
    """The GitHub API refuses until `reset` (seconds since the epoch)."""

    def __init__(self, reset):
        super().__init__(reset)
        self.reset = reset


# The network


def rate_limit_reset(status, headers, now):
    """The time at which a rate-limited answer allows the next request, or
    None if the answer is not a rate limit."""
    headers = {key.lower(): value for key, value in headers.items()}
    if status not in (403, 429):
        return None
    try:
        if "retry-after" in headers:
            return now + int(headers["retry-after"])
        if headers.get("x-ratelimit-remaining") == "0":
            return int(headers["x-ratelimit-reset"])
    except (KeyError, ValueError):
        return None
    return None


class Internet:
    """Every request of the script: HTTP GET, git ls-remote, git clone.
    `opener` is the HTTP transport (urlopen); `clock` paces the attempts."""

    def __init__(self, opener=urllib.request.urlopen, clock=time):
        self.opener = opener
        self.clock = clock

    def get(self, url):
        """The body of `url`, or None if the server answers 404.

        A body that arrives cut short is continued from the bytes already
        received, with a Range request that names the first answer's
        validator (If-Range: its strong ETag, else its Last-Modified). An
        answer that is not the asked continuation starts the body again
        from zero; without a validator, so does every attempt. The body is
        complete when a read ends without being cut and its length is the
        total that the server announced (Content-Length of the first answer,
        or the total of a Content-Range), if it announced one. At most
        HTTP_ATTEMPTS requests, HTTP_PAUSE seconds apart; the last failure is
        raised."""
        assert url.startswith("https://"), url
        body, validator, length, failure = b"", None, None, None
        for attempt in range(1, HTTP_ATTEMPTS + 1):
            if attempt > 1:
                self.clock.sleep(HTTP_PAUSE)
            headers = {"User-Agent": USER_AGENT}
            if body and validator:
                headers["Range"] = f"bytes={len(body)}-"
                headers["If-Range"] = validator
            else:
                body = b""
            request = urllib.request.Request(url, headers=headers)
            try:
                with self.opener(request, timeout=HTTP_TIMEOUT) as response:
                    if body and not _continues(response, len(body)):
                        body = b""
                        if response.status == 206:  # a part from elsewhere
                            failure = http.client.IncompleteRead(b"")
                            continue
                    if not body:
                        validator = _validator(response.headers)
                        length = _length(response.headers)
                    elif length is None:  # a continuation may tell the total
                        length = _range_total(response.headers)
                    cut = False
                    try:
                        body += response.read()
                    except http.client.IncompleteRead as error:
                        body += error.partial
                        failure, cut = error, True
            except urllib.error.HTTPError as error:
                reset = rate_limit_reset(error.code, error.headers, time.time())
                if error.code not in (404, 416) and reset is None:
                    raise
                error.close()
                if error.code == 404:
                    return None
                if reset is not None:
                    raise RateLimited(reset) from None
                body, failure = b"", error  # 416: the range is not served
                continue
            except (http.client.HTTPException, OSError) as error:
                failure = error  # a failed connection: try again
                continue
            if cut:  # never complete, whatever the length
                continue
            if length is None or len(body) == length:
                return body
            if len(body) > length:
                body = b""
            failure = http.client.IncompleteRead(body, max(0, length - len(body)))
        raise failure

    def ls_remote(self, repository):
        """The output of git ls-remote of the tags, or None if there is no
        such repository."""
        result = _git("ls-remote", "--tags", "--refs", "--", repository)
        if result.returncode == 0:
            return result.stdout.decode()
        error = result.stderr.decode(errors="replace").lower()
        if "not found" in error or "could not read username" in error:
            return None
        raise RuntimeError(f"git ls-remote {repository}: {error.strip()}")

    def clone(self, repository, tag, destination, needed):
        """The objects of the tag, read from git's object store; nothing is
        checked out, so no hook, filter or line-ending conversion applies.

        Two bare repositories fetch the explicit ref refs/tags/<tag>: one
        with its whole history and without blobs, one with the tree of the
        tag (depth 1). Returns {tag_object, commit, commits, authors,
        files}: the object that the tag ref names, the commit that it peels
        to, the commits reachable from it and their distinct author e-mails
        (without case), {path: blob id} of the regular files of its tree
        (no symbolic link, no submodule), and too_large: the paths for which
        `needed(path)` holds whose blob is over MAX_BLOB_BYTES. The other
        needed blobs are written to destination/blobs/<blob id>, as
        committed, one record at a time from git cat-file --batch, after
        git cat-file --batch-check gave their sizes."""
        destination = Path(destination)
        ref = f"refs/tags/{tag}"
        history, tree = destination / "history.git", destination / "tree.git"
        for bare in (history, tree):
            _git_output("init", "--quiet", "--bare", "--template=", str(bare))
        settings = (
            ("core.repositoryformatversion", "1"),
            ("extensions.partialclone", "origin"),
            ("remote.origin.url", repository),
            ("remote.origin.promisor", "true"),
            ("remote.origin.partialclonefilter", "blob:none"),
        )
        for name, value in settings:
            _git_output("-C", str(history), "config", name, value)
        _git_output(
            *("-C", str(history), "fetch", "--quiet", "--no-tags"),
            *("--filter=blob:none", "origin", f"+{ref}:{ref}"),
        )
        _git_output(
            *("-C", str(tree), "fetch", "--quiet", "--no-tags", "--depth=1"),
            *("--", repository, f"+{ref}:{ref}"),
        )
        tag_object = _git_output("-C", str(tree), "rev-parse", ref).strip()
        if _git_output("-C", str(history), "rev-parse", ref).strip() != tag_object:
            raise RuntimeError(f"{repository}: the tag {tag} moved during the fetch")
        commit = _git_output("-C", str(tree), "rev-parse", f"{ref}^{{commit}}")
        commit = commit.strip()
        log = _git_output("-C", str(history), "log", "--format=%ae", commit)
        emails = {line.strip().lower() for line in log.splitlines() if line.strip()}
        commits = int(_git_output("-C", str(history), "rev-list", "--count", commit))
        files = {}
        listing = _git_bytes(
            "-C", str(tree), "ls-tree", "-r", "-z", "--full-tree", commit
        )
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            meta, _, path = entry.partition(b"\t")
            mode, kind, oid = meta.decode().split()
            if kind == "blob" and mode in ("100644", "100755"):
                files[path.decode("utf-8", "replace")] = oid
        wanted = {files[path] for path in files if needed(path)}
        sizes = _blob_sizes(tree, sorted(wanted))
        too_large = sorted(
            path
            for path in files
            if needed(path) and sizes[files[path]] > MAX_BLOB_BYTES
        )
        expected = [
            (oid, size) for oid, size in sorted(sizes.items()) if size <= MAX_BLOB_BYTES
        ]
        blobs = destination / "blobs"
        blobs.mkdir()
        wanted_list = destination / "wanted.txt"
        wanted_list.write_text("".join(f"{oid}\n" for oid, _ in expected))
        with open(wanted_list, "rb") as requests:
            process = subprocess.Popen(
                ["git", "-C", str(tree), "cat-file", "--batch"],
                stdin=requests,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=git_environment(os.environ),
            )
            try:
                copy_blobs(process.stdout, expected, blobs)
            finally:
                process.stdout.close()
                status = process.wait()
        if status != 0:
            raise RuntimeError(f"git cat-file --batch exited with {status}")
        return {
            "tag_object": tag_object,
            "commit": commit,
            "commits": commits,
            "authors": len(emails),
            "files": dict(sorted(files.items())),
            "too_large": too_large,
        }


def _blob_sizes(repository, oids):
    """{blob id: size} from git cat-file --batch-check; every record must
    be the blob that was asked."""
    data = "".join(f"{oid}\n" for oid in oids).encode()
    output = _git_bytes("-C", str(repository), "cat-file", "--batch-check", data=data)
    lines = output.decode().splitlines()
    if len(lines) != len(oids):
        raise RuntimeError("git cat-file --batch-check: not one record per object")
    sizes = {}
    for oid, line in zip(oids, lines, strict=True):
        fields = line.split()
        if len(fields) != 3 or fields[0] != oid or fields[1] != "blob":
            raise RuntimeError(f"git cat-file --batch-check: {line!r} for {oid}")
        sizes[oid] = int(fields[2])
    return sizes


def copy_blobs(stream, expected, directory):
    """Copy the records of git cat-file --batch from `stream` to
    directory/<blob id>, one at a time, for the expected [(blob id, size)]
    in order. Each record must be `<id> blob <size>\\n`, the payload of that
    size, and `\\n`; nothing may follow the last one."""
    for oid, size in expected:
        header = stream.readline(200)
        if not header:
            raise RuntimeError(f"git cat-file: the output is too short, at {oid}")
        if header != f"{oid} blob {size}\n".encode():
            raise RuntimeError(f"git cat-file: header {header[:80]!r} for {oid}")
        with open(Path(directory, oid), "wb") as blob:
            left = size
            while left:
                chunk = stream.read(min(left, 1 << 20))
                if not chunk:
                    raise RuntimeError(f"git cat-file: the blob {oid} is cut")
                blob.write(chunk)
                left -= len(chunk)
        if stream.read(1) != b"\n":
            raise RuntimeError(f"git cat-file: no delimiter after {oid}")
    if stream.read(1):
        raise RuntimeError("git cat-file: output after the last record")


def _validator(headers):
    """The validator for If-Range: a strong ETag, else Last-Modified."""
    etag = headers.get("ETag")
    if etag and not etag.startswith("W/"):
        return etag
    return headers.get("Last-Modified")


def _length(headers):
    """The length of the whole body that a first answer announces
    (Content-Length), or None."""
    length = headers.get("Content-Length")
    return int(length) if length and length.isdigit() else None


def _range_total(headers):
    """The length of the whole body that a part announces (the total of
    Content-Range: bytes a-b/total), or None when it is `*`. The part's own
    Content-Length is the length of the part only."""
    total = (headers.get("Content-Range") or "").rpartition("/")[2]
    return int(total) if total.isdigit() else None


def _continues(response, offset):
    """Whether an answer is the continuation from `offset` that was asked."""
    content_range = response.headers.get("Content-Range") or ""
    return response.status == 206 and content_range.startswith(f"bytes {offset}-")


TRANSPORT_SETTINGS = ("http.",)  # the caller's git settings that a child keeps


def git_environment(environ):
    """The environment of a git child: no GIT_* variable of the caller and
    neither the user's nor the system's configuration; no prompt, no LFS
    download. Of the git settings that the caller passes in its
    environment (GIT_CONFIG_PARAMETERS, GIT_CONFIG_KEY_n and _VALUE_n),
    only those of TRANSPORT_SETTINGS stay: a sandbox's proxy may need
    http.proxyAuthMethod. They pass on in GIT_CONFIG_PARAMETERS, where a
    setting without a value (true) differs from an empty one, in the order
    in which git applies them (the indexed ones first): the last one of a
    key wins, as for the caller."""
    settings = []  # (key, value or None), in the order in which git applies them
    for number in range(int(environ.get("GIT_CONFIG_COUNT", "0") or 0)):
        key = environ.get(f"GIT_CONFIG_KEY_{number}", "")
        settings.append((key, environ.get(f"GIT_CONFIG_VALUE_{number}", "")))
    for item in shlex.split(environ.get("GIT_CONFIG_PARAMETERS", "")):
        key, separator, value = item.partition("=")
        settings.append((key, value if separator else None))
    kept = [
        _quoted(key) if value is None else f"{_quoted(key)}={_quoted(value)}"
        for key, value in settings
        if key.lower().startswith(TRANSPORT_SETTINGS)
    ]
    environment = {
        name: value for name, value in environ.items() if not name.startswith("GIT_")
    }
    environment.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_LFS_SKIP_SMUDGE="1",
    )
    if kept:
        environment["GIT_CONFIG_PARAMETERS"] = " ".join(kept)
    return environment


def _quoted(text):
    """`text` quoted as git quotes the items of GIT_CONFIG_PARAMETERS."""
    return "'" + text.replace("'", "'\\''") + "'"


def _git(*args, data=None):
    """Run git in git_environment."""
    environment = git_environment(os.environ)
    return subprocess.run(
        ["git", *args], input=data, capture_output=True, env=environment
    )


def _git_bytes(*args, data=None):
    """The output of a git command that must succeed."""
    result = _git(*args, data=data)
    if result.returncode != 0:
        error = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args[2:4])}: {error}")
    return result.stdout


def _git_output(*args):
    return _git_bytes(*args).decode()


class Cache:
    """The responses of the network, kept under `work`. Without `internet`
    (--offline), a response that is not in the cache is an error. On a
    rate-limit answer it waits, with `clock`, until the limit resets."""

    def __init__(self, work, internet, clock):
        self.work = Path(work)
        self.internet = internet
        self.clock = clock

    def _fetch(self, fetch):
        while True:
            try:
                return fetch()
            except RateLimited as limit:
                wait = max(0, math.ceil(limit.reset - self.clock.time())) + 1
                until = datetime.datetime.fromtimestamp(limit.reset, datetime.UTC)
                print(
                    f"The GitHub API rate limit is reached: waiting {wait} s, "
                    f"until {until:%Y-%m-%d %H:%M:%S} UTC.",
                    file=sys.stderr,
                    flush=True,
                )
                self.clock.sleep(wait)

    def _keep(self, kind, key, fetch):
        path = self.work / "cache" / kind / hashlib.sha256(key.encode()).hexdigest()
        missing = path.with_suffix(".missing")
        if path.exists():
            return path.read_bytes()
        if missing.exists():
            return None
        if self.internet is None:
            raise Offline(f"not in the cache under {self.work}: {key}")
        data = self._fetch(fetch)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_atomic(missing if data is None else path, data or b"")
        return data

    def get(self, url):
        return self._keep("http", url, lambda: self.internet.get(url))

    def json(self, url):
        data = self.get(url)
        return None if data is None else json.loads(data)

    def ls_remote(self, repository):
        data = self._keep(
            "git",
            repository,
            lambda: _encode(self.internet.ls_remote(repository)),
        )
        return None if data is None else data.decode()

    def clone(self, repository, tag, modules):
        """(directory, facts) of the objects of a tag: Internet.clone wrote
        the directory (its blobs/) and gave the facts (clone.json). The
        blobs read are those that needed_blobs(modules) names."""
        identity = json.dumps([repository, tag, sorted(modules)])
        key = hashlib.sha256(identity.encode()).hexdigest()[:24]
        entry = self.work / "tags" / key
        if not entry.exists():
            if self.internet is None:
                raise Offline(f"not in the cache under {self.work}: {repository} {tag}")
            entry.parent.mkdir(parents=True, exist_ok=True)
            partial = Path(tempfile.mkdtemp(dir=entry.parent, prefix="partial-"))
            facts = self.internet.clone(repository, tag, partial, needed_blobs(modules))
            (partial / "clone.json").write_text(json.dumps(facts, sort_keys=True))
            partial.rename(entry)  # the entry appears complete or not at all
        return entry, json.loads((entry / "clone.json").read_text())


def _encode(text):
    return None if text is None else text.encode()


def _write_atomic(path, data):
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(data)
    os.replace(temporary, path)


# Names and versions


def normalise(name):
    """The name as PyPI compares names (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


_VERSION = re.compile(
    r"""v?(?:(?P<epoch>[0-9]+)!)?(?P<release>[0-9]+(?:\.[0-9]+)*)
    (?:[-_.]?(?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)[-_.]?(?P<pre_n>[0-9]+)?)?
    (?:-(?P<post_n1>[0-9]+)|[-_.]?(?P<post_l>post|rev|r)[-_.]?(?P<post_n2>[0-9]+)?)?
    (?:[-_.]?(?P<dev_l>dev)[-_.]?(?P<dev_n>[0-9]+)?)?""",
    re.VERBOSE | re.IGNORECASE,
)
_PRE_ORDER = {"a": 0, "alpha": 0, "b": 1, "beta": 1}  # c, pre, preview, rc: 2


def parse_version(text):
    """A PEP 440 version as {release, pre, post, dev, key}, or None. `key`
    orders versions as PEP 440 does; a local version is not accepted."""
    match = _VERSION.fullmatch(text.strip())
    if match is None:
        return None
    release = tuple(int(part) for part in match["release"].split("."))
    pre = (
        None
        if match["pre_l"] is None
        else (_PRE_ORDER.get(match["pre_l"].lower(), 2), int(match["pre_n"] or 0))
    )
    post_text = match["post_n1"] or match["post_n2"]
    post = None
    if match["post_n1"] is not None or match["post_l"] is not None:
        post = int(post_text or 0)
    dev = None if match["dev_l"] is None else int(match["dev_n"] or 0)
    trimmed = list(release)
    while len(trimmed) > 1 and trimmed[-1] == 0:
        trimmed.pop()
    if pre is None:
        pre_key = (0,) if dev is not None and post is None else (2,)
    else:
        pre_key = (1, *pre)
    key = (
        int(match["epoch"] or 0),
        tuple(trimmed),
        pre_key,
        (0,) if post is None else (1, post),
        (1,) if dev is None else (0, dev),
    )
    epoch = int(match["epoch"] or 0)
    return {
        "epoch": epoch,
        "release": release,
        "pre": pre,
        "post": post,
        "dev": dev,
        "key": key,
    }


_CLAUSE = re.compile(r"\s*(~=|===|==|!=|<=|>=|<|>)\s*([^\s,]+)\s*")


def admits(specifier, text):
    """Whether the version `text` satisfies the PEP 440 specifier set.
    Raises ValueError for a specifier that cannot be read."""
    version = parse_version(text)
    for clause in specifier.split(","):
        if not clause.strip():
            continue
        match = _CLAUSE.fullmatch(clause)
        if match is None:
            raise ValueError(clause.strip())
        if not _clause_admits(match[1], match[2], version, text):
            return False
    return True


def _starts_with(version, prefix):
    """Whether `version` is in the series of `prefix` (PEP 440 prefix
    matching): the same epoch, and the release, padded with zeros, starts
    with the prefix's release."""
    size = len(prefix["release"])
    padded = (version["release"] + (0,) * size)[:size]
    return version["epoch"] == prefix["epoch"] and padded == prefix["release"]


def _clause_admits(operator, target, version, text):
    if operator == "===":
        return text.strip() == target
    if version is None:
        raise ValueError(f"{text} is not a version")
    if target.endswith(".*") and operator in ("==", "!="):
        prefix = parse_version(target[:-2])
        if prefix is None:
            raise ValueError(target)
        return _starts_with(version, prefix) == (operator == "==")
    wanted = parse_version(target)
    if wanted is None:
        raise ValueError(target)
    if operator == "~=":
        if len(wanted["release"]) < 2:
            raise ValueError(f"~={target}")
        prefix = {"epoch": wanted["epoch"], "release": wanted["release"][:-1]}
        return version["key"] >= wanted["key"] and _starts_with(version, prefix)
    compare = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
    }[operator]
    return compare(version["key"], wanted["key"])


# Environment markers (PEP 508), for CPython 3.14 on Linux

_MARKER_TOKEN = re.compile(
    r"""\s*(?:(?P<string>'[^']*'|"[^"]*")|(?P<op>~=|===|==|!=|<=|>=|<|>|\(|\))
    |(?P<word>[A-Za-z_][A-Za-z0-9_.]*))""",
    re.VERBOSE,
)


class MarkerError(Exception):
    pass


def evaluate_marker(text, environment):
    """The value of a marker; every comparison is evaluated, so that a
    variable outside `environment` is an error wherever it is."""
    tokens, position = [], 0
    text = text.strip()
    while position < len(text):
        match = _MARKER_TOKEN.match(text, position)
        if match is None or match.end() == position:
            raise MarkerError(f"cannot read {text[position:]!r}")
        kind = match.lastgroup
        tokens.append((kind, match[kind]))
        position = match.end()
    parser = _MarkerParser(tokens, environment)
    value = parser.disjunction()
    if parser.position != len(tokens):
        raise MarkerError(f"cannot read {text!r}")
    return value


class _MarkerParser:
    def __init__(self, tokens, environment):
        self.tokens = tokens
        self.position = 0
        self.environment = environment

    def peek(self):
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return (None, None)

    def take(self):
        token = self.peek()
        if token[0] is None:
            raise MarkerError("the marker ends early")
        self.position += 1
        return token

    def disjunction(self):
        values = [self.conjunction()]
        while self.peek() == ("word", "or"):
            self.take()
            values.append(self.conjunction())
        return any(values)

    def conjunction(self):
        values = [self.atom()]
        while self.peek() == ("word", "and"):
            self.take()
            values.append(self.atom())
        return all(values)

    def atom(self):
        if self.peek() == ("op", "("):
            self.take()
            value = self.disjunction()
            if self.take() != ("op", ")"):
                raise MarkerError("a parenthesis is not closed")
            return value
        left = self.value()
        kind, operator = self.take()
        if (kind, operator) == ("word", "not"):
            if self.take() != ("word", "in"):
                raise MarkerError("'not' without 'in'")
            operator = "not in"
        elif (kind, operator) != ("word", "in") and (
            kind != "op" or operator in ("(", ")")
        ):
            raise MarkerError(f"{operator!r} is not an operator")
        return compare_marker_values(left, operator, self.value())

    def value(self):
        kind, text = self.take()
        if kind == "string":
            return text[1:-1]
        if kind == "word" and text not in ("and", "or", "in", "not"):
            if text not in self.environment:
                raise MarkerError(f"the marker uses {text}")
            return self.environment[text]
        raise MarkerError(f"{text!r} is not a value")


def compare_marker_values(left, operator, right):
    """`left operator right` as PEP 508 compares: as versions when both
    sides are versions, else as Python strings (~= and === have no string
    form)."""
    if operator == "in":
        return left in right
    if operator == "not in":
        return left not in right
    if parse_version(left) is not None:
        try:
            return admits(f"{operator}{right}", left)
        except ValueError:
            pass
    strings = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
    }
    if operator not in strings:  # ~= and === compare only versions
        raise MarkerError(f"cannot compare {left!r} {operator} {right!r}")
    return strings[operator](left, right)


# Code lines (the definition of the hand selection's count.py)


def code_lines(data):
    """Lines with code: the lines of the tokens of every statement that is
    not a string statement. A string statement (a docstring, say) starts its
    logical line and has only string literals, not formatted ones, and
    parentheses: "doc", ("a" "b"). The string after `def f():` on the same
    line, or after a `;`, does not start its logical line: it is code.
    Comments and blank lines are not code. A file that `tokenize` cannot
    read counts its non-blank lines."""
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(data).readline))
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError):
        text = data.decode("utf-8", "replace")
        return sum(1 for line in text.splitlines() if line.strip())
    skipped = (
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
        tokenize.ENCODING,
    )
    lines, statement, depth = set(), [], 0
    first = True  # the statement starts its logical line

    def close():
        if not first or not all(
            token.type == tokenize.STRING or token.string in ("(", ")")
            for token in statement
        ):
            for token in statement:
                lines.update(range(token.start[0], token.end[0] + 1))
        statement.clear()

    for token in tokens:
        if token.type in skipped:
            continue
        if token.type == tokenize.NEWLINE:
            close()
            first = True
            continue
        if token.type == tokenize.OP:
            if token.string in ("(", "[", "{"):
                depth += 1
            elif token.string in (")", "]", "}"):
                depth -= 1
            elif token.string == ";" and depth == 0:
                close()
                first = False
                continue
        statement.append(token)
    close()
    return len(lines)


# The packages under evaluation


class Candidate:
    """A package under evaluation. `facts` go to the frame; `data` holds
    what later filters need."""

    def __init__(self, name, rank, pinned=None):
        self.name = name
        self.rank = rank  # None: not in the list
        self.pinned = pinned  # check NAME==VERSION
        self.facts = {}
        self.data = {}
        self.github = None  # the GitHub facts, once fetched

    def need(self, key):
        if key not in self.data:
            raise NotEvaluated(key)
        return self.data[key]


class Context:
    def __init__(self, network, date):
        self.network = network
        self.date = date  # the list date D


def metadata(candidate, context):
    """The PyPI metadata of the release (its `info`)."""
    if "info" not in candidate.data:
        version = candidate.need("version")
        url = PYPI_RELEASE.format(name=candidate.name, version=version)
        data = context.network.json(url)
        candidate.data["info"] = None if data is None else data["info"]
    if candidate.data["info"] is None:
        raise NotEvaluated("the metadata of the release")
    return candidate.data["info"]


def needed_blobs(modules):
    """Whether the filters need the blob of a path of the tree: a test-file
    candidate (tests), or a path that ends in a module path of the wheel
    (released-code)."""
    modules = set(modules)

    def needed(path):
        parts = path.split("/")
        if any(fnmatch.fnmatch(parts[-1], form) for form in TEST_FILES):
            return True
        return any("/".join(parts[start:]) in modules for start in range(len(parts)))

    return needed


def checkout(candidate, context):
    """The tree of the tag, from the object store: (directory, {path: blob
    id} of its regular files, the needed paths whose blob is too large).
    The other needed blobs are in directory/blobs."""
    if "checkout" not in candidate.data:
        directory, found = context.network.clone(
            candidate.need("repository"),
            candidate.need("tag"),
            sorted(candidate.data.get("modules", {})),
        )
        candidate.data["checkout"] = (directory, found["files"])
        candidate.data["too_large"] = set(found["too_large"])
        candidate.data["history"] = found
        candidate.facts["tag_object"] = found["tag_object"]
        candidate.facts["commit"] = found["commit"]
    return candidate.data["checkout"]


def _blob(directory, files, path):
    """The content of a .py file of the tree, as committed."""
    return Path(directory, "blobs", files[path]).read_bytes()


# The filters: each returns None (pass) or the reason of the failure.


def rank(candidate, context):
    """1. The download rank is at most RANK_CUTOFF."""
    if candidate.rank is None:
        return "not in the list"
    if RANK_CUTOFF is not None and candidate.rank > RANK_CUTOFF:
        return f"rank {candidate.rank}, beyond {RANK_CUTOFF}"
    return None


def not_a_stub(candidate, context):
    """2. Not a stub package by its name."""
    name = normalise(candidate.name)
    if name.startswith(STUB_PREFIXES) or name.endswith(STUB_SUFFIXES):
        return "a stub package by its name"
    return None


def _upload_date(file):
    stamp = file.get("upload_time_iso_8601") or file["upload_time"]
    return datetime.date.fromisoformat(stamp[:10])


def release(candidate, context):
    """3. The latest final release on or before the list date, not yanked,
    uploaded in the MAINTAINED_YEARS before that date."""
    project = context.network.json(PYPI_PROJECT.format(name=candidate.name))
    if project is None:
        return "not on PyPI"
    found = []
    for text, files in project.get("releases", {}).items():
        version = parse_version(text)
        if version is not None:
            found.append((version, text, files))
    if candidate.pinned is not None:
        pinned = parse_version(candidate.pinned)
        if pinned is None:
            return f"{candidate.pinned!r} is not a version"
        matches = [entry for entry in found if entry[0]["key"] == pinned["key"]]
        if not matches:
            return f"release {candidate.pinned} not on PyPI"
        version, text, files = matches[0]
        files = [file for file in files if not file.get("yanked")]
        if version["pre"] is not None or version["dev"] is not None:
            return f"{text} is a pre-release"
        if not files:
            return f"{text} is yanked"
        before = [file for file in files if _upload_date(file) <= context.date]
        if not before:  # check goes on with the release that it names
            _keep_release(candidate, text, files)
            return f"{text} was uploaded after {context.date}"
        files = before
    else:
        eligible = []
        for version, text, files in found:
            files = [
                file
                for file in files
                if not file.get("yanked") and _upload_date(file) <= context.date
            ]
            if files and version["pre"] is None and version["dev"] is None:
                eligible.append((version["key"], text, files))
        if not eligible:
            return f"no final release on or before {context.date} that is not yanked"
        _, text, files = max(eligible, key=lambda entry: entry[0])
    uploaded = _keep_release(candidate, text, files)
    limit = _years_before(context.date, MAINTAINED_YEARS)
    if uploaded < limit:
        return f"{text} was uploaded on {uploaded}, before {limit}"
    return None


def _keep_release(candidate, text, files):
    """Record the release for the later filters; returns its upload date."""
    uploaded = min(_upload_date(file) for file in files)
    candidate.facts["release"] = text
    candidate.facts["uploaded"] = uploaded.isoformat()
    candidate.data["version"] = text
    candidate.data["files"] = files
    return uploaded


def _years_before(date, years):
    try:
        return date.replace(year=date.year - years)
    except ValueError:  # 29 February
        return date.replace(year=date.year - years, day=28)


def _wheel_tag(filename):
    parts = filename.removesuffix(".whl").split("-")
    return "-".join(parts[-3:]) if len(parts) >= 5 else None


def pure_python(candidate, context):
    """4. An sdist and at least one wheel, every wheel pure Python."""
    files = candidate.need("files")
    wheels = sorted(
        (file for file in files if file["packagetype"] == "bdist_wheel"),
        key=lambda file: file["filename"],
    )
    if not any(file["packagetype"] == "sdist" for file in files):
        return "no sdist"
    if not wheels:
        return "no wheel"
    for wheel in wheels:
        if _wheel_tag(wheel["filename"]) not in PURE_WHEEL_TAGS:
            return f"wheel {wheel['filename']} is not pure Python"
    candidate.data["wheel"] = wheels[0]
    candidate.facts["wheel"] = {
        "filename": wheels[0]["filename"],
        "url": wheels[0]["url"],
        "sha256": wheels[0]["digests"]["sha256"],
    }
    return None


def python_version(candidate, context):
    """5. requires_python admits TARGET_PYTHON (no requirement admits it)."""
    requires = metadata(candidate, context).get("requires_python") or ""
    try:
        if admits(requires, TARGET_PYTHON):
            return None
    except ValueError as error:
        return f"cannot read requires_python {requires!r}: {error}"
    return f"requires_python {requires!r} excludes Python {TARGET_PYTHON}"


def _permissive(identifier):
    return identifier.lower() in {name.lower() for name in PERMISSIVE_LICENCES}


def licence(candidate, context):
    """6. The licence that PyPI states is permissive: license_expression,
    else the licence classifiers, else a license field that is one
    identifier. A licence that PyPI does not state is left to `github`."""
    info = metadata(candidate, context)
    expression = (info.get("license_expression") or "").strip()
    classifiers = [
        classifier
        for classifier in info.get("classifiers") or []
        if classifier.startswith("License ::")
        and classifier != "License :: OSI Approved"
    ]
    field = (info.get("license") or "").strip()
    if expression:
        # Every licence that the expression names must be permissive; an
        # exception (WITH) is not accepted.
        names = [
            word
            for word in re.split(r"[\s()]+", expression)
            if word and word.upper() not in ("AND", "OR")
        ]
        if not all(_permissive(name) for name in names):
            return f"licence {expression!r} is not permissive"
        stated, source = expression, "license_expression"
    elif classifiers:
        if not all(classifier in PERMISSIVE_CLASSIFIERS for classifier in classifiers):
            return f"licence classifiers {classifiers} are not all permissive"
        stated, source = "; ".join(classifiers), "classifiers"
    elif field and not any(character.isspace() for character in field):
        if not _permissive(field):
            return f"licence field {field[:40]!r} is not permissive"
        stated, source = field, "license"
    else:  # no licence, or a text that is not an identifier
        candidate.data["licence_undecided"] = True
        return None
    candidate.facts["licence"] = stated
    candidate.facts["licence_source"] = source
    return None


def no_dependency(candidate, context):
    """7. No requirement that applies on CPython 3.14 on Linux without an
    extra."""
    for requirement in metadata(candidate, context).get("requires_dist") or []:
        name, _, marker = requirement.partition(";")
        if marker.strip():
            try:
                applies = evaluate_marker(marker, MARKER_ENVIRONMENT)
            except MarkerError as error:
                return f"cannot evaluate the marker of {requirement!r}: {error}"
        else:
            applies = True
        if applies:
            return f"requires {name.strip()}"
    return None


def _unsafe(member):
    return (
        member.startswith("/")
        or "\\" in member
        or re.match(r"[A-Za-z]:", member) is not None
        or ".." in member.split("/")
    )


# What reading a member of a zip archive can raise on malformed data.
_MEMBER_ERRORS = (
    RuntimeError,
    NotImplementedError,
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    OSError,
    ValueError,
)


def size(candidate, context):
    """8. The code lines of the wheel's modules, without test directories
    and metadata, are within MIN_CODE_LINES and MAX_CODE_LINES."""
    wheel = candidate.need("wheel")
    data = context.network.get(wheel["url"])
    if data is None:
        return f"wheel {wheel['url']} not found"
    if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
        return "the wheel's SHA-256 differs from PyPI's"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            for info in members:
                if _unsafe(info.filename):
                    return f"unsafe member path {info.filename!r} in the wheel"
            modules = {}
            for info in members:
                name = info.filename
                if not name.endswith(".py") or name.split("/")[0].endswith(
                    (".dist-info", ".data")
                ):
                    continue
                if info.flag_bits & 0x1:
                    return f"member {name} of the wheel is encrypted"
                try:
                    modules[name] = archive.read(info)
                except _MEMBER_ERRORS as error:
                    return f"cannot read member {name} of the wheel: {error}"
    except _MEMBER_ERRORS as error:  # also names that cannot be decoded
        return f"the wheel cannot be read as a zip file: {error}"
    lines = {name: code_lines(content) for name, content in modules.items()}
    counted = [
        name for name in modules if not set(name.split("/")[:-1]) & set(TEST_DIRS)
    ]
    total = sum(lines[name] for name in counted)
    candidate.data["modules"] = modules
    candidate.data["module_lines"] = lines
    candidate.data["code_lines"] = total
    candidate.facts["code_lines"] = total
    candidate.facts["top_level"] = sorted(
        {name.split("/")[0].removesuffix(".py") for name in counted}
    )
    if not MIN_CODE_LINES <= total <= MAX_CODE_LINES:
        return f"{total} code lines, not within {MIN_CODE_LINES} to {MAX_CODE_LINES}"
    return None


_GITHUB = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_NOT_OWNERS = {"sponsors", "orgs", "users", "apps", "marketplace", "topics"}


def github_repositories(info):
    """[(owner, repo)] of the GitHub repositories that the project's URLs
    name, in order, without duplicates (GitHub names ignore case)."""
    urls = list((info.get("project_urls") or {}).values()) + [info.get("home_page")]
    found = {}
    for url in urls:
        match = _GITHUB.match((url or "").strip())
        if match is None or match[1].lower() in _NOT_OWNERS:
            continue
        repo = match[2].removesuffix(".git")
        found.setdefault((match[1].lower(), repo.lower()), (match[1], repo))
    return list(found.values())


def source(candidate, context):
    """9. One GitHub repository, with a tag of the release."""
    version = candidate.need("version")
    repositories = github_repositories(metadata(candidate, context))
    if not repositories:
        return "no GitHub repository in project_urls or home_page"
    if len(repositories) > 1:
        named = ", ".join(f"{owner}/{repo}" for owner, repo in repositories)
        return f"several GitHub repositories: {named}"
    owner, repo = repositories[0]
    candidate.data["github_repository"] = (owner, repo)
    url = f"https://github.com/{owner}/{repo}"
    candidate.facts["repository"] = url
    listing = context.network.ls_remote(url)
    if listing is None:
        return f"repository {url} not found"
    tags = {}  # {tag: the object that refs/tags/<tag> names}
    for line in listing.splitlines():
        oid, _, ref = line.partition("\t")
        if ref.startswith("refs/tags/"):
            tags[ref.removeprefix("refs/tags/")] = oid.strip()
    forms = [form.format(version=version, name=candidate.name) for form in TAG_FORMS]
    for tag in forms:
        if tag in tags:
            candidate.data["repository"] = url
            candidate.data["tag"] = tag
            candidate.data["tag_object"] = tags[tag]
            candidate.facts["tag"] = tag
            return None
    return f"no tag for {version} (tried {', '.join(forms)})"


def history(candidate, context):
    """10. At the tag: at least MIN_COMMITS commits and MIN_AUTHORS commit
    authors (by e-mail)."""
    checkout(candidate, context)
    found = candidate.data["history"]
    listed = candidate.need("tag_object")
    if found["tag_object"] != listed:
        return (
            f"the tag {candidate.need('tag')} names {found['tag_object']}, "
            f"not {listed} as git ls-remote listed"
        )
    candidate.facts["commits"] = found["commits"]
    candidate.facts["authors"] = found["authors"]
    if found["commits"] < MIN_COMMITS:
        return f"{found['commits']} commits at the tag, fewer than {MIN_COMMITS}"
    if found["authors"] < MIN_AUTHORS:
        return f"{found['authors']} commit author, fewer than {MIN_AUTHORS}"
    return None


def ci(candidate, context):
    """11. A CI configuration at the tag (one of CI_FILES)."""
    _, files = checkout(candidate, context)
    found = [
        path
        for path in files
        if any(
            path.startswith(entry) if entry.endswith("/") else path == entry
            for entry in CI_FILES
        )
    ]
    candidate.facts["ci"] = found
    return None if found else "no CI configuration"


# A test, by a rule on the text that is the same on every Python version: a
# `def test...(` on one line (with type parameters on that line or not), or
# a class line without type parameters whose bases name something that ends
# in TestCase. The rule reads text: such a line inside a string, or TestCase
# in a comment, counts too; type parameters over several lines, and a class
# with type parameters, do not count.
_TEST_FUNCTION = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+test\w*[ \t]*(?:\[.*?\])?[ \t]*\(", re.M
)
_TEST_CASE = re.compile(r"^[ \t]*class[ \t]+\w+[ \t]*\([^)]*TestCase\b", re.M)


def _holds_a_test(content):
    """Whether a file, decoded as UTF-8, has a test by the rule above."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return bool(_TEST_FUNCTION.search(text) or _TEST_CASE.search(text))


def tests(candidate, context):
    """12. A file test_*.py or *_test.py anywhere in the checkout that holds
    a test (_TEST_FUNCTION or _TEST_CASE). Records the test-to-code line
    ratio. A file over MAX_BLOB_BYTES is not read and does not count."""
    directory, files = checkout(candidate, context)
    too_large = candidate.data["too_large"]
    found, lines, skipped = [], 0, []
    for path in files:
        if not any(fnmatch.fnmatch(path.rsplit("/", 1)[-1], f) for f in TEST_FILES):
            continue
        if path in too_large:
            skipped.append(path)
            continue
        content = _blob(directory, files, path)
        if _holds_a_test(content):
            found.append(path)
            lines += code_lines(content)
    candidate.facts["test_files"] = found
    candidate.facts["test_code_lines"] = lines
    package = candidate.need("code_lines")
    candidate.facts["test_ratio"] = round(lines / package, 3) if package else None
    if found:
        return None
    reason = "no test file with a test function or TestCase"
    if skipped:
        reason += f" (over the size limit: {', '.join(skipped[:5])})"
    return reason


def released_code(candidate, context):
    """13. The wheel's modules that are missing from the checkout or differ
    from it hold at most MAX_DIFFERING_PERCENT of the wheel's code lines.
    A file of the checkout over MAX_BLOB_BYTES is not read and differs."""
    modules = candidate.need("modules")
    lines = candidate.need("module_lines")
    directory, files = checkout(candidate, context)
    too_large = candidate.data["too_large"]
    total = sum(lines.values())

    def differing(prefix):
        return [
            name
            for name in sorted(modules)
            if prefix + name not in files
            or prefix + name in too_large
            or _blob(directory, files, prefix + name) != modules[name]
        ]

    # Where the checkout has the wheel's modules: "" or "src/", say.
    prefixes = {""}
    for name in modules:
        prefixes.update(
            path.removesuffix(name) for path in files if path.endswith("/" + name)
        )
    root, missing = min(
        ((prefix, differing(prefix)) for prefix in prefixes),
        key=lambda found: (sum(lines[n] for n in found[1]), len(found[0]), found[0]),
    )
    differ = sum(lines[name] for name in missing)
    candidate.facts["released_code"] = {
        "source_root": root.rstrip("/") or ".",
        "differing_files": missing,
        "differing_lines": differ,
        "lines": total,
    }
    if 100 * differ > MAX_DIFFERING_PERCENT * total:
        share = 100 * differ / total
        named = ", ".join(missing[:5]) + (", ..." if len(missing) > 5 else "")
        return (
            f"{share:.1f}% of the wheel's code lines are not in the checkout as "
            f"released (at most {MAX_DIFFERING_PERCENT}%): {named}"
        )
    return None


def github(candidate, context):
    """14. The GitHub repository has at least MIN_STARS stars, is not
    archived and not a fork; when PyPI stated no licence, GitHub's detected
    licence is permissive."""
    owner, repo = candidate.need("github_repository")
    data = context.network.json(GITHUB_API.format(owner=owner, repo=repo))
    if data is None:
        candidate.github = {"found": False}
        return "repository not found by the GitHub API"
    detected = (data.get("license") or {}).get("spdx_id")
    candidate.github = {key: data[key] for key in GITHUB_FACTS if key in data}
    candidate.github["license"] = detected
    stars = data.get("stargazers_count", 0)
    if stars < MIN_STARS:
        return f"{stars} stars, fewer than {MIN_STARS}"
    if data.get("archived"):
        return "the repository is archived"
    if data.get("fork"):
        return "the repository is a fork"
    if candidate.data.get("licence_undecided"):
        if detected is None or not _permissive(detected):
            return (
                f"PyPI states no licence, and GitHub's licence {detected} "
                "is not permissive"
            )
        candidate.facts["licence"] = detected
        candidate.facts["licence_source"] = "GitHub"
    return None


FILTERS = (  # in this order: cheap ones first, the GitHub API last
    ("rank", rank),
    ("stub-name", not_a_stub),
    ("release", release),
    ("pure-python", pure_python),
    ("requires-python", python_version),
    ("licence", licence),
    ("no-dependency", no_dependency),
    ("size", size),
    ("source", source),
    ("history", history),
    ("ci", ci),
    ("tests", tests),
    ("released-code", released_code),
    ("github", github),
)


def evaluate(candidate, context, keep_going=False):
    """[(filter name, None or reason)]: up to the first failure, or all of
    them with `keep_going` (a filter without its inputs: "not evaluated")."""
    results = []
    for name, check in FILTERS:
        try:
            reason = check(candidate, context)
        except NotEvaluated as missing:
            reason = f"not evaluated: needs {missing}"
        results.append((name, reason))
        if reason is not None and not keep_going:
            break
    return results


# The list, the projects already used and the log


def read_list(path):
    """(bytes, date, [(rank, name)]) of the list; rank 1 is the most
    downloaded."""
    data = Path(path).read_bytes()
    document = json.loads(data)
    date = datetime.date.fromisoformat(document["last_update"][:10])
    ranked, seen = [], set()
    for position, row in enumerate(document["rows"], start=1):
        if normalise(row["project"]) not in seen:
            seen.add(normalise(row["project"]))
            ranked.append((position, row["project"]))
    return data, date, ranked


def list_record(path, data, date, ranked):
    return {
        "file": Path(path).name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "date": date.isoformat(),
        "rows": len(ranked),
    }


def seed_of(data, round_number):
    digest = hashlib.sha256(data + b"\n" + f"round {round_number}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def used_names(directories, excluded):
    """{normalised name: why it is skipped}: the projects of each benchmark
    directory and the exclusions. Raises ValueError for an exclusion
    without a reason."""
    used = {}
    for directory in directories:
        path = Path(directory) / "projects.toml"
        with open(path, "rb") as stream:
            names = tomllib.load(stream)
        for name in names:
            used.setdefault(normalise(name), f"used: {_shown(path)}")
    lines = Path(excluded).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError(
                f"{_shown(excluded)}:{number}: an exclusion needs a reason"
            )
        used.setdefault(normalise(parts[0]), f"excluded: {parts[1].strip()}")
    return used


def _shown(path):
    """A path as the log shows it: relative to the repository if inside it."""
    path = Path(path).resolve()
    if path.is_relative_to(REPOSITORY_ROOT):
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    return path.name


def constants():
    """The constants of the procedure, for the logs: the thresholds, the
    URLs and the filters in their order."""
    paths = ("HERE", "REPOSITORY_ROOT", "SELECTION_DIR", "LIST_PATH")
    paths += ("EXCLUDED_PATH", "FRAME_PATH", "USED_DIRS")
    logged = {
        name: value
        for name, value in globals().items()
        if name.isupper()
        and not name.startswith(("_", "HTTP_"))
        and name not in (*paths, "FILTERS", "USER_AGENT")
    }
    logged["FILTERS"] = [name for name, _ in FILTERS]
    return logged


def _write_log(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


# The commands


def other_python(command):
    """Whether this Python is not FRAME_PYTHON; then says so. frame and
    check run only on FRAME_PYTHON: the code-line count depends on the
    tokenizer of the Python version."""
    if sys.version_info[:2] == tuple(FRAME_PYTHON):
        return False
    wanted = ".".join(map(str, FRAME_PYTHON))
    running = ".".join(map(str, sys.version_info[:2]))
    print(
        f"{command} runs only on Python {wanted} (FRAME_PYTHON): the code-line "
        f"count depends on the tokenizer of the Python version. This is Python "
        f"{running}.",
        file=sys.stderr,
    )
    return True


def run_frame(args, network):
    """Evaluate the list up to RANK_CUTOFF and write the frame."""
    if other_python("frame"):
        return 2
    data, date, ranked = read_list(args.list)
    context = Context(network, date)
    funnel = {name: [0, 0] for name, _ in FILTERS}
    inside = sum(
        1 for position, _ in ranked if RANK_CUTOFF is None or position <= RANK_CUTOFF
    )
    packages = []
    for position, name in ranked:
        candidate = Candidate(name, position)
        results = evaluate(candidate, context)
        for filter_name, reason in results:
            funnel[filter_name][0] += 1
            funnel[filter_name][1] += reason is not None
        if results[0][1] is not None:  # beyond the cut-off: counted only
            continue
        entry = {"name": name, "rank": position}
        entry["release"] = candidate.facts.get("release")
        failed, reason = results[-1]
        if reason is None:
            entry.update(
                result="pass", facts={**candidate.facts, "github": candidate.github}
            )
        else:
            entry.update(result="fail", filter=failed, reason=reason)
            if candidate.github is not None:
                entry["github"] = candidate.github
        packages.append(entry)
        shown = "pass" if reason is None else f"{failed}: {reason}"
        print(
            f"[{len(packages)}/{inside}] {name}: {shown}", file=sys.stderr, flush=True
        )
    rows = [
        {"filter": name, "reached": reached, "rejected": rejected}
        for name, (reached, rejected) in funnel.items()
    ]
    document = {
        "list": list_record(args.list, data, date, ranked),
        "constants": constants(),
        "python": "{}.{}".format(*sys.version_info[:2]),
        "funnel": rows,
        "passed": sum(1 for entry in packages if entry["result"] == "pass"),
        "packages": packages,
    }
    _write_log(args.out or FRAME_PATH, document)
    print("| # | Filter | Reached | Rejected | Passed |")
    print("|---|---|---|---|---|")
    for number, row in enumerate(rows, start=1):
        passed = row["reached"] - row["rejected"]
        print(
            f"| {number} | {row['filter']} | {row['reached']} | {row['rejected']} "
            f"| {passed} |"
        )
    return 0


def strata_of(passing):
    """The passing packages sorted by code lines, then name, cut into
    STRATA strata of equal count; the first (count mod STRATA) strata have
    one package more."""
    ordered = sorted(
        passing, key=lambda entry: (entry["facts"]["code_lines"], entry["name"])
    )
    base, extra = divmod(len(ordered), STRATA)
    strata, start = [], 0
    for number in range(STRATA):
        end = start + base + (1 if number < extra else 0)
        strata.append(ordered[start:end])
        start = end
    return strata


def run_draw(args):
    """Draw one package per stratum from the frozen frame."""
    frame_bytes = Path(args.frame).read_bytes()
    frame = json.loads(frame_bytes)
    data, date, ranked = read_list(args.list)
    if hashlib.sha256(data).hexdigest() != frame["list"]["sha256"]:
        print(
            "The list's SHA-256 is not the one that the frame records.", file=sys.stderr
        )
        return 2
    try:
        used = used_names([*USED_DIRS, *args.used], args.excluded)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    drops = {}
    for entry in args.drop:
        name, separator, reason = entry.partition("=")
        if not separator or not name.strip() or not reason.strip():
            print(f"--drop needs NAME=REASON: {entry!r}", file=sys.stderr)
            return 2
        drops[normalise(name)] = reason.strip()
    passing = [entry for entry in frame["packages"] if entry["result"] == "pass"]
    if len(passing) < STRATA:
        print(
            f"The frame has {len(passing)} passing packages, fewer than the "
            f"{STRATA} strata.",
            file=sys.stderr,
        )
        return 2
    strata = strata_of(passing)
    seed = seed_of(data, args.round)
    order = sorted(entry["name"] for entry in passing)
    random.Random(seed).shuffle(order)
    stratum_of = {
        entry["name"]: number
        for number, members in enumerate(strata)
        for entry in members
    }
    by_name = {entry["name"]: entry for entry in passing}
    logged, dropped, reached = [], [], set()
    for number, members in enumerate(strata):
        examined, selected = [], None
        for name in order:
            if stratum_of[name] != number:
                continue
            key = normalise(name)
            if key in used:
                examined.append(
                    {"name": name, "result": "skipped", "reason": used[key]}
                )
            elif key in drops:
                reached.add(key)
                examined.append(
                    {"name": name, "result": "dropped", "reason": drops[key]}
                )
                dropped.append({"name": name, "reason": drops[key]})
            else:
                examined.append({"name": name, "result": "selected"})
                chosen = by_name[name]
                selected = {
                    "name": name,
                    "rank": chosen["rank"],
                    "facts": chosen["facts"],
                }
                break
        logged.append(
            {
                "stratum": number + 1,
                "members": [entry["name"] for entry in members],
                "min_code_lines": members[0]["facts"]["code_lines"],
                "max_code_lines": members[-1]["facts"]["code_lines"],
                "examined": examined,
                "selected": selected,
            }
        )
    if set(drops) - reached:
        unknown = ", ".join(sorted(set(drops) - reached))
        print(
            f"--drop names packages that the draw did not reach: {unknown}",
            file=sys.stderr,
        )
        return 2
    selected = [
        stratum["selected"]["name"] for stratum in logged if stratum["selected"]
    ]
    log = {
        "list": list_record(args.list, data, date, ranked),
        "frame": {
            "file": Path(args.frame).name,
            "sha256": hashlib.sha256(frame_bytes).hexdigest(),
        },
        "round": args.round,
        "seed": seed,
        "constants": constants(),
        "used": dict(sorted(used.items())),
        "order": order,
        "strata": logged,
        "complete": len(selected) == STRATA,
        "selected": selected,
        "dropped": dropped,
    }
    _write_log(args.out or SELECTION_DIR / f"round-{args.round}.json", log)
    print(f"Round {args.round}, seed {seed}, frame of {len(passing)} packages")
    print()
    print("| Stratum | Code lines | Packages | Selected | Skipped |")
    print("|---|---|---|---|---|")
    for stratum in logged:
        skipped = [
            f"{e['name']} ({e['reason']})" for e in stratum["examined"] if "reason" in e
        ]
        chosen = stratum["selected"]["name"] if stratum["selected"] else "-"
        print(
            f"| {stratum['stratum']} | {stratum['min_code_lines']} to "
            f"{stratum['max_code_lines']} | {len(stratum['members'])} | {chosen} "
            f"| {'; '.join(skipped)} |"
        )
    if not log["complete"]:
        print("A stratum has no package left to select.", file=sys.stderr)
        return 1
    return 0


def run_check(args, network):
    """Every filter on named packages, all of them even after a failure."""
    if other_python("check"):
        return 2
    _, date, ranked = read_list(args.list)
    ranks = {normalise(name): position for position, name in ranked}
    context = Context(network, date)
    rows, facts = [], []
    for wanted in args.names:
        name, _, pinned = wanted.partition("==")
        candidate = Candidate(name, ranks.get(normalise(name)), pinned or None)
        for filter_name, reason in evaluate(candidate, context, keep_going=True):
            result = "pass" if reason is None else reason
            if reason is not None and not reason.startswith("not evaluated"):
                result = f"fail: {reason}"
            rows.append(
                f"| {name} | {candidate.facts.get('release', '-')} | {filter_name} "
                f"| {result} |"
            )
        found = candidate.github or {}
        shown = [
            _shown_value(found.get(key, "-"))
            for key in ("stargazers_count", "forks_count", "archived", "fork")
        ]
        shown += [str(found.get(key, "-"))[:10] for key in ("created_at", "pushed_at")]
        shown += [
            _shown_value(candidate.facts.get(key, "-"))
            for key in ("code_lines", "commits", "authors", "test_ratio", "licence")
        ]
        facts.append(f"| {name} | {candidate.rank or '-'} | {' | '.join(shown)} |")
    print(
        f"List of {date}. The check writes no frame and no round log; "
        f"it fills the cache under {args.work}."
    )
    print()
    print("| Package | Release | Filter | Result |")
    print("|---|---|---|---|")
    print("\n".join(rows))
    print()
    print(
        "| Package | Rank | Stars | Forks | Archived | Fork | Created | Pushed "
        "| Code lines | Commits | Authors | Test ratio | Licence |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    print("\n".join(facts))
    return 0


def _shown_value(value):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def main(argv=None, internet=None, clock=time):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    frame = commands.add_parser("frame", help="evaluate the list, write the frame")
    frame.add_argument("--work", type=Path, required=True, help="cache and clones")
    frame.add_argument("--offline", action="store_true", help="never fetch")
    frame.add_argument("--list", type=Path, default=LIST_PATH)
    frame.add_argument("--out", type=Path, help="default: selection/frame.json")
    chosen = commands.add_parser("draw", help="draw a batch from the frame")
    chosen.add_argument("--round", type=int, required=True)
    chosen.add_argument("--used", action="append", default=[], metavar="DIR")
    chosen.add_argument("--drop", action="append", default=[], metavar="NAME=REASON")
    chosen.add_argument("--list", type=Path, default=LIST_PATH)
    chosen.add_argument("--frame", type=Path, default=FRAME_PATH)
    chosen.add_argument("--excluded", type=Path, default=EXCLUDED_PATH)
    chosen.add_argument("--out", type=Path, help="default: selection/round-N.json")
    check = commands.add_parser("check", help="evaluate named packages")
    check.add_argument("names", nargs="+", metavar="NAME[==VERSION]")
    check.add_argument("--work", type=Path, required=True, help="cache and clones")
    check.add_argument("--offline", action="store_true", help="never fetch")
    check.add_argument("--list", type=Path, default=LIST_PATH)
    args = parser.parse_args(argv)
    if args.command == "draw":
        return run_draw(args)
    if not args.offline and internet is None:
        internet = Internet(clock=clock)
    network = Cache(args.work, None if args.offline else internet, clock)
    try:
        if args.command == "frame":
            return run_frame(args, network)
        return run_check(args, network)
    except Offline as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
