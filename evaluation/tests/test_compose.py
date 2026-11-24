import json
import re
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
REPOSITORY = EVALUATION.parent
COMPOSE = EVALUATION / "compose.yaml"
DIGEST = re.compile(r"[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}")


def _scalar(text, anchors):
    text = text.strip()
    if text.startswith("*"):
        return anchors[text[1:]]
    if text.startswith("["):
        return json.loads(text)
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return {"true": True, "false": False}.get(text, text)


def read_plain_yaml(text):
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            lines.append((len(raw) - len(raw.lstrip(" ")), stripped))
    anchors = {}

    def block(i, indent):
        if lines[i][1].startswith("- "):
            items = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1][:2] == "- ":
                items.append(_scalar(lines[i][1][2:], anchors))
                i += 1
            return items, i
        mapping = {}
        while i < len(lines) and lines[i][0] == indent:
            key, _, rest = lines[i][1].partition(":")
            rest, anchor = rest.strip(), None
            if rest.startswith("&"):
                anchor, _, rest = rest[1:].partition(" ")
            i += 1
            if rest:
                value = _scalar(rest, anchors)
            else:
                value, i = block(i, lines[i][0])
            if anchor:
                anchors[anchor] = value
            if key == "<<":
                mapping = {**value, **mapping}
            else:
                mapping[key] = value
        return mapping, i

    document, end = block(0, 0)
    assert end == len(lines), f"not read: {lines[end:]}"
    return document


@pytest.fixture(scope="module")
def compose():
    return read_plain_yaml(COMPOSE.read_text(encoding="utf-8"))


def test_the_python_image_is_pinned_by_digest_in_the_file_once(compose):
    text = COMPOSE.read_text(encoding="utf-8")
    assert len(re.findall(r"@sha256:[0-9a-f]{64}", text)) == 1
    assert DIGEST.fullmatch(compose["x-python-image"])


def test_the_default_base_of_the_inputs_image_is_the_python_image(compose):
    text = (EVALUATION / "container" / "Dockerfile.inputs").read_text()
    assert f"ARG PYTHON_IMAGE={compose['x-python-image']}\n" in text
    inputs = compose["services"]["inputs"]["build"]["args"]
    assert inputs["PYTHON_IMAGE"] == compose["x-python-image"]


def _dockerfile(service):
    build = service["build"]
    return (EVALUATION / build["context"] / build["dockerfile"]).resolve()


def test_every_service_is_sealed(compose):
    for name, service in compose["services"].items():
        where = f"service {name}"
        assert service.get("network_mode") == "none", where
        assert service.get("read_only") is True, where
        assert service.get("cap_drop") == ["ALL"], where
        assert "no-new-privileges:true" in service.get("security_opt", []), where
        assert not service.get("privileged"), where
        user = service.get("user", "")
        assert user and not user.startswith(("0", "root")), where
        assert service.get("mem_limit") and service.get("tmpfs"), where
        for volume in service.get("volumes", []):
            assert "docker.sock" not in volume, where
            source, target, *mode = volume.split(":")
            writable = "ro" not in mode
            allowed = (source, target) == ("./results/trace", "/results/trace")
            assert not writable or allowed, f"{where}: {volume} is writable"


def test_every_image_is_built_from_a_pinned_base(compose):
    for name, service in compose["services"].items():
        if "build" not in service:
            assert DIGEST.fullmatch(service["image"]), name
            continue
        dockerfile = _dockerfile(service)
        assert dockerfile.is_relative_to(REPOSITORY), name
        text = dockerfile.read_text(encoding="utf-8")
        assert "FROM ${PYTHON_IMAGE}" in text, name
        assert DIGEST.fullmatch(service["build"]["args"]["PYTHON_IMAGE"]), name


def test_the_services_are_the_inputs_and_the_trace_which_takes_only_name(compose):
    assert list(compose["services"]) == ["inputs", "trace"]
    assert compose["services"]["trace"]["entrypoint"][4:] == ["${NAME:-unset}"]
    assert "SET" not in re.findall(r"\$\{(\w+)", COMPOSE.read_text())


def test_the_trace_service_gives_the_wheels_built_here_as_a_build_context(compose):
    contexts = compose["services"]["trace"]["build"]["additional_contexts"]
    assert contexts["wheels"] == "macro-benchmark/wheels"
    assert (EVALUATION / contexts["wheels"]).is_dir()


def test_the_trace_service_writes_only_its_own_directory(compose):
    writable = [
        volume
        for volume in compose["services"]["trace"]["volumes"]
        if not volume.endswith(":ro")
    ]
    assert writable == ["./results/trace:/results/trace"]
    assert (EVALUATION / "results" / "trace" / ".gitkeep").is_file()
