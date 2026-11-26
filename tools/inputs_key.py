import argparse
import hashlib
import re
import sys
from pathlib import Path

DESCRIPTION = """\
Prints the content key of the evaluation inputs images (pycg-eval-macro and
pycg-eval-runner, built from evaluation/container/Dockerfile.inputs): the
SHA-256 of BUILD_FILES, every file that the build reads, and of the
PYTHON_IMAGE build argument, x-python-image of COMPOSE. Two checkouts with
the same key build the same images, so the key is the tag under which CI
publishes them and `make eval-inputs` pulls them.
"""

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = "evaluation/container/Dockerfile.inputs"
DOCKERIGNORE = "evaluation/container/Dockerfile.inputs.dockerignore"
COPIED_FILES = (
    "evaluation/container/fetch.py",
    "evaluation/macro-benchmark/projects.py",
    "evaluation/macro-benchmark/projects.toml",
    "evaluation/scale/projects.py",
    "evaluation/scale/projects.toml",
)
BUILD_FILES = (DOCKERFILE, DOCKERIGNORE, *COPIED_FILES)
COMPOSE = "evaluation/compose.yaml"
PYTHON_IMAGE = re.compile(r"^x-python-image: &python-image (\S+)$", re.MULTILINE)


class InputsKeyError(Exception):
    pass


def python_image(root):
    found = PYTHON_IMAGE.findall((root / COMPOSE).read_text(encoding="utf-8"))
    if len(found) != 1:
        raise InputsKeyError(f"{COMPOSE}: {len(found)} x-python-image lines, not one")
    return found[0]


def inputs_key(root):
    lines = []
    for path in sorted(BUILD_FILES):
        digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
        lines.append(f"{digest}  {path}\n")
    lines.append(f"PYTHON_IMAGE={python_image(root)}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    try:
        print(inputs_key(ROOT))
    except (OSError, InputsKeyError) as error:
        print(f"inputs_key: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
