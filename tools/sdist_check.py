import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

DESCRIPTION = """\
Builds the source distribution with `uv build --sdist` and fails when it
holds a file of the Rust program (RUST_PATHS), which the Python package
never ships, or lacks the package itself (REQUIRED_PATHS). Prints one line
per finding.
"""

ROOT = Path(__file__).resolve().parents[1]
RUST_PATHS = (
    "Cargo.toml",
    "Cargo.lock",
    "clippy.toml",
    "rust-toolchain.toml",
    "crates/",
)
REQUIRED_PATHS = ("pyproject.toml", "pycg/__init__.py")


def relative_names(members):
    return [name.partition("/")[2] for name in members if "/" in name]


def findings_of(members):
    names = relative_names(members)
    findings = [
        f"the sdist holds {name}"
        for name in names
        if any(
            name.startswith(path) if path.endswith("/") else name == path
            for path in RUST_PATHS
        )
    ]
    findings += [
        f"the sdist lacks {path}" for path in REQUIRED_PATHS if path not in names
    ]
    return findings


def built_members(root):
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(
            ["uv", "build", "--sdist", "--quiet", "--out-dir", out, str(root)],
            check=True,
        )
        (archive,) = Path(out).glob("*.tar.gz")
        with tarfile.open(archive) as sdist:
            return sdist.getnames()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    findings = findings_of(built_members(ROOT))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
