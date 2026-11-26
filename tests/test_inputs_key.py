import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "tools_inputs_key", ROOT / "tools" / "inputs_key.py"
)
inputs_key = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inputs_key)
WORKFLOW = ROOT / ".github" / "workflows" / "inputs.yml"


def copied_sources(dockerfile_text):
    sources = []
    for instruction in dockerfile_text.replace("\\\n", " ").splitlines():
        words = instruction.split()
        if not words or words[0] != "COPY":
            continue
        if any(word.startswith("--from=") for word in words[1:]):
            continue
        arguments = [word for word in words[1:] if not word.startswith("--")]
        sources.extend(arguments[:-1])
    return sources


def let_in(dockerignore_text):
    return [line[1:] for line in dockerignore_text.splitlines() if line.startswith("!")]


def test_the_key_covers_every_path_the_dockerfile_copies():
    text = (ROOT / inputs_key.DOCKERFILE).read_text(encoding="utf-8")
    sources = copied_sources(text)
    assert sources
    assert set(sources) - set(inputs_key.COPIED_FILES) == set()


def test_a_copied_path_outside_the_key_is_found():
    text = (
        "FROM x AS a\nCOPY a.py \\\n    evaluation/new.py dest/\nCOPY --from=a /x /y\n"
    )
    assert copied_sources(text) == ["a.py", "evaluation/new.py"]


def test_the_key_covers_every_file_the_build_context_lets_in():
    text = (ROOT / inputs_key.DOCKERIGNORE).read_text(encoding="utf-8")
    assert sorted(let_in(text)) == sorted(inputs_key.COPIED_FILES)


def test_the_workflow_runs_when_an_input_of_the_key_changes():
    lines = {line.strip() for line in WORKFLOW.read_text(encoding="utf-8").splitlines()}
    watched = (
        *inputs_key.BUILD_FILES,
        inputs_key.COMPOSE,
        "tools/inputs_key.py",
        ".github/workflows/inputs.yml",
    )
    for path in watched:
        assert f"- {path}" in lines, path


@pytest.fixture
def checkout(tmp_path):
    for path in (*inputs_key.BUILD_FILES, inputs_key.COMPOSE):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, tmp_path / path)
    return tmp_path


def test_the_key_is_a_sha256_that_is_the_same_on_every_run(checkout):
    key = inputs_key.inputs_key(checkout)
    assert len(key) == 64
    assert set(key) <= set("0123456789abcdef")
    assert inputs_key.inputs_key(checkout) == key
    assert inputs_key.inputs_key(ROOT) == key


@pytest.mark.parametrize("path", inputs_key.BUILD_FILES)
def test_the_key_changes_with_every_file_of_the_build(checkout, path):
    key = inputs_key.inputs_key(checkout)
    with (checkout / path).open("ab") as file:
        file.write(b"\n")
    assert inputs_key.inputs_key(checkout) != key


def test_the_key_changes_with_the_python_image(checkout):
    key = inputs_key.inputs_key(checkout)
    compose = checkout / inputs_key.COMPOSE
    text = compose.read_text(encoding="utf-8")
    compose.write_text(text.replace("@sha256:", "@sha256:0", 1), encoding="utf-8")
    assert inputs_key.inputs_key(checkout) != key


def test_the_key_does_not_change_with_the_rest_of_compose(checkout):
    key = inputs_key.inputs_key(checkout)
    with (checkout / inputs_key.COMPOSE).open("a", encoding="utf-8") as file:
        file.write("\n")
    assert inputs_key.inputs_key(checkout) == key


def test_a_compose_without_the_python_image_is_an_error(checkout):
    (checkout / inputs_key.COMPOSE).write_text("name: pycg\n", encoding="utf-8")
    with pytest.raises(inputs_key.InputsKeyError, match="0 x-python-image lines"):
        inputs_key.inputs_key(checkout)


def test_the_command_prints_the_key_of_the_checkout():
    done = subprocess.run(
        [sys.executable, "-I", str(ROOT / "tools" / "inputs_key.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == inputs_key.inputs_key(ROOT) + "\n"
