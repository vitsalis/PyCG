#!/bin/sh
# Runs inside the container of trace.sh: entry.sh NAME.
#
# The image holds the project at its pin, from the inputs image, in
# /inputs/macro-benchmark/projects/NAME; /tracer holds the tracer and the
# benchmark's projects.toml (read-only); /out is the only writable mount.
# The source is copied to a work directory on the tmpfs, so that the tests
# may write next to themselves; trace.py compares its files before and
# after the run.
set -eu

name=$1
work=/tmp/work
python=$(command -v python3)

mkdir -p "$work/projects"
cp -RP /tracer/benchmark/. "$work/"
cp -RP "/inputs/macro-benchmark/projects/$name" "$work/projects/$name"

"$python" -I -c 'import platform; print("python:", platform.python_version(), platform.machine(), platform.libc_ver()[0])'
# Where the package is found, without importing it: in the copy of the
# source, and nowhere in the environment.
"$python" -I -B /tracer/evaluation/macro-benchmark/trace.py "$name" \
    --benchmark-dir "$work" --locate
exec "$python" -I -B /tracer/evaluation/macro-benchmark/trace.py "$name" \
    --python "$python" --benchmark-dir "$work" --output /out/trace.json
