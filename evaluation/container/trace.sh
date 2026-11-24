#!/bin/sh
# Record the trace of one macro-benchmark project in a container.
#
#   PYTHON_IMAGE=python:3.14-slim@sha256:<digest> \
#       evaluation/container/trace.sh [--dry-run] BENCHMARK_DIR NAME
#
# The project's source comes from the inputs image (pycg-evaluation-inputs,
# built by `docker compose -f evaluation/compose.yaml build inputs`; its
# build checked the source against its pin). The script:
# 1. checks that the pin of NAME in projects.toml is that of its round log
#    (for an sdist, that the sdist names the release of its round log);
# 2. builds the image of NAME from Dockerfile.trace,
#    BENCHMARK_DIR/test-environments/NAME.txt (the only file of the context) and
#    the source of NAME in the inputs image;
# 3. copies the tracer, projects.toml and the project's pytest plugins to
#    a temporary directory;
# 4. runs the tests under the tracer in a container without network, with
#    two mounts: the tracer (read-only) and the output;
# 5. checks the trace and copies it to BENCHMARK_DIR/dynamic/NAME.json; the
#    distributions of the container go to test-environments/NAME.installed.txt;
# 6. removes the temporary directory and any container left.
#
# --dry-run prints the commands and runs nothing. Docker gets only PATH,
# HOME, DOCKER_HOST and DOCKER_CONFIG of the caller's environment.
set -eu

usage() {
    echo "usage: PYTHON_IMAGE=NAME@sha256:DIGEST $0 [--dry-run] BENCHMARK_DIR NAME" >&2
    exit 2
}

dry_run=0
if [ "${1:-}" = "--dry-run" ]; then
    dry_run=1
    shift
fi
[ $# -eq 2 ] || usage
benchmark=$(cd "$1" && pwd)
name=$2
case $name in
    '' | . | .. | *[!A-Za-z0-9_.-]*) echo "trace.sh: bad project name: $name" >&2; exit 2 ;;
esac

here=$(cd "$(dirname "$0")" && pwd)
repository=$(cd "$here/../.." && pwd)
requirements=$benchmark/test-environments/$name.txt
uid=10001
container=pycg-trace-$name-$$
step="check the arguments"
work=""

quote() {
    case $1 in
        *[!A-Za-z0-9_./:=@,+-]* | '') printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")" ;;
        *) printf '%s' "$1" ;;
    esac
}

# Print a command in dry-run mode, else run it.
run() {
    if [ "$dry_run" = 1 ]; then
        line=""
        for arg in "$@"; do
            line="$line $(quote "$arg")"
        done
        printf '%s\n' "${line# }"
    else
        "$@"
    fi
}

docker_cli() {
    if [ "$dry_run" = 1 ]; then
        # shellcheck disable=SC2016 # printed as it is, not expanded
        prefix='env -i PATH="$PATH" HOME="$HOME"'
        if [ -n "${DOCKER_HOST:-}" ]; then
            prefix="$prefix DOCKER_HOST=$(quote "$DOCKER_HOST")"
        fi
        if [ -n "${DOCKER_CONFIG:-}" ]; then
            prefix="$prefix DOCKER_CONFIG=$(quote "$DOCKER_CONFIG")"
        fi
        printf '%s %s\n' "$prefix" "$(run docker "$@")"
    else
        env -i PATH="$PATH" HOME="$HOME" \
            ${DOCKER_HOST:+"DOCKER_HOST=$DOCKER_HOST"} \
            ${DOCKER_CONFIG:+"DOCKER_CONFIG=$DOCKER_CONFIG"} \
            docker "$@"
    fi
}

helper() {
    python3 -I "$here/trace_helper.py" "$@"
}

cleanup() {
    status=$?
    if [ "$dry_run" = 0 ]; then
        if [ "$step" = "4 run the tests in the container" ] && [ "$status" -ne 0 ]; then
            docker_cli rm --force "$container" >/dev/null 2>&1 || true
        fi
        if [ -n "$work" ] && [ -d "$work" ]; then
            # The temporary directory goes to the trash where there is one
            # (recoverable); else it stays, and its path is printed.
            if command -v trash >/dev/null 2>&1; then
                trash "$work"
            else
                echo "trace.sh: left the temporary directory $work" >&2
            fi
        fi
    fi
    if [ "$status" -ne 0 ]; then
        echo "trace.sh: $name: step '$step' failed" >&2
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

if [ -z "${PYTHON_IMAGE:-}" ]; then
    if [ "$dry_run" = 0 ]; then
        echo "trace.sh: set PYTHON_IMAGE to python:3.14-slim@sha256:<digest>" >&2
        exit 2
    fi
    zeros=0000000000000000000000000000000000000000000000000000000000000000
    PYTHON_IMAGE="python:3.14-slim@sha256:$zeros"  # a placeholder digest
fi
[ -f "$requirements" ] || { echo "trace.sh: no $requirements" >&2; exit 2; }

step="1 check the pin"
helper check-pin "$benchmark" "$name"

step="2 build the image"
tag=$(helper image-tag "$name" "$here/Dockerfile.trace" "$requirements" "$PYTHON_IMAGE")
if [ "$dry_run" = 1 ]; then
    work="<work>"
else
    work=$(mktemp -d "${TMPDIR:-/tmp}/pycg-trace.XXXXXX")
    mkdir "$work/context" "$work/tracer" "$work/out"
    cp "$here/Dockerfile.trace" "$work/context/Dockerfile"
    cp "$requirements" "$work/context/requirements.txt"
fi
docker_cli build --pull=false --network=default \
    --build-context inputs=docker-image://pycg-inputs \
    --build-arg "PYTHON_IMAGE=$PYTHON_IMAGE" --build-arg "NAME=$name" \
    --tag "$tag" "$work/context"

step="3 prepare the mount of the tracer"
if [ "$dry_run" = 0 ]; then
    mkdir -p "$work/tracer/evaluation/macro-benchmark" "$work/tracer/micro-benchmark" \
        "$work/tracer/benchmark"
    cp "$repository/evaluation/macro-benchmark/trace.py" \
        "$repository/evaluation/macro-benchmark/projects.py" \
        "$work/tracer/evaluation/macro-benchmark/"
    cp "$repository/micro-benchmark/validate.py" "$work/tracer/micro-benchmark/"
    cp "$here/entry.sh" "$work/tracer/"
    cp "$benchmark/projects.toml" "$work/tracer/benchmark/"
    for plugin in $(helper plugins "$benchmark" "$name"); do
        mkdir -p "$work/tracer/benchmark/$(dirname "$plugin")"
        cp "$benchmark/$plugin" "$work/tracer/benchmark/$plugin"
    done
    chmod -R a+rX "$work/tracer"
    chmod 0755 "$work"
    chmod 0777 "$work/out"
fi

step="4 run the tests in the container"
docker_cli run --rm --name "$container" \
    --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --pids-limit 512 \
    --memory 6g --memory-swap 6g --cpus 4 --user "$uid:$uid" \
    --tmpfs /tmp:rw,size=1g --tmpfs /home/runner:rw,size=256m \
    -e HOME=/home/runner -e PYTHONHASHSEED=0 -e PYTHONDONTWRITEBYTECODE=1 \
    --mount "type=bind,source=$work/tracer,target=/tracer,readonly" \
    --mount "type=bind,source=$work/out,target=/out" \
    "$tag" sh /tracer/entry.sh "$name"

step="5 check and copy the trace"
if [ "$dry_run" = 1 ]; then
    echo "python3 -I $(quote "$here/trace_helper.py") check-trace '<work>/out/trace.json'" \
        "$(quote "$benchmark") $name $(quote "$PYTHON_IMAGE")"
else
    helper check-trace "$work/out/trace.json" "$benchmark" "$name" "$PYTHON_IMAGE"
fi

step="6 clean up"
