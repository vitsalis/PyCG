import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
REPOSITORY = EVALUATION.parent
CONTAINER = EVALUATION / "container"
BENCHMARK = EVALUATION / "macro-benchmark"
WHEELS = BENCHMARK / "wheels"
_spec = importlib.util.spec_from_file_location(
    "trace_helper", CONTAINER / "trace_helper.py"
)
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)

PYTHON_IMAGE = "python:3.14-slim@sha256:" + "ab" * 32


def image_inputs(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM x\n")
    requirements = tmp_path / "demo.txt"
    requirements.write_text("demo==1.0 --hash=sha256:" + "0" * 64 + "\n")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    return dockerfile, requirements, wheels


def test_the_image_tag_hashes_the_wheels(tmp_path):
    dockerfile, requirements, wheels = image_inputs(tmp_path)
    tag = helper.image_tag("Demo", dockerfile, requirements, PYTHON_IMAGE, wheels)
    assert tag.startswith("pycg-trace-demo:") and len(tag.split(":")[1]) == 12
    assert (
        helper.image_tag("Demo", dockerfile, requirements, PYTHON_IMAGE, wheels) == tag
    )
    (wheels / "a-1.0-py3-none-any.whl").write_bytes(b"one")
    added = helper.image_tag("Demo", dockerfile, requirements, PYTHON_IMAGE, wheels)
    assert added != tag
    (wheels / "a-1.0-py3-none-any.whl").write_bytes(b"two")
    changed = helper.image_tag("Demo", dockerfile, requirements, PYTHON_IMAGE, wheels)
    assert changed not in (tag, added)
    (wheels / "a-1.0-py3-none-any.whl").rename(wheels / "b-1.0-py3-none-any.whl")
    renamed = helper.image_tag("Demo", dockerfile, requirements, PYTHON_IMAGE, wheels)
    assert renamed not in (tag, added, changed)


def test_the_image_tag_needs_a_directory_of_wheels(tmp_path):
    dockerfile, requirements, wheels = image_inputs(tmp_path)
    with pytest.raises(helper.HelperError, match="not a directory"):
        helper.image_tag("demo", dockerfile, requirements, PYTHON_IMAGE, wheels / "x")


def test_the_dockerfile_installs_from_the_wheels_by_hash_and_removes_them():
    text = (CONTAINER / "Dockerfile.trace").read_text()
    assert "COPY --from=wheels . /opt/pycg-trace/wheels/" in text
    install = text[text.index("pip install") : text.index("pip uninstall")]
    for flag in (
        "--require-hashes",
        "--only-binary :all:",
        "--no-deps",
        "--find-links /opt/pycg-trace/wheels",
    ):
        assert flag in install, flag
    assert "rm -r /opt/pycg-trace/wheels" in text


def test_trace_sh_gives_the_repository_s_wheels_to_the_build_and_the_tag():
    env = {
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", "/"),
        "PYTHON_IMAGE": PYTHON_IMAGE,
    }
    done = subprocess.run(
        ["sh", str(CONTAINER / "trace.sh"), "--dry-run", str(BENCHMARK), "tinydb"],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    build = next(line for line in done.stdout.splitlines() if " build " in line)
    assert f"--build-context wheels={WHEELS}" in build
    tag = helper.image_tag(
        "tinydb",
        CONTAINER / "Dockerfile.trace",
        BENCHMARK / "test-environments" / "tinydb.txt",
        PYTHON_IMAGE,
        WHEELS,
    )
    assert f"--tag {tag}" in build


def test_every_wheel_built_here_is_pinned_and_has_its_clean_check():
    wheels = sorted(WHEELS.glob("*.whl"))
    assert wheels
    pins = "".join(
        p.read_text() for p in (BENCHMARK / "test-environments").glob("*.txt")
    )
    for wheel in wheels:
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert f"--hash=sha256:{digest}" in pins, wheel.name
        report = json.loads(Path(f"{wheel}.check.json").read_text())
        assert report["sha256"] == digest and report["problems"] == [], wheel.name
