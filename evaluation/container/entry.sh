#!/bin/sh
set -eu

name=$1
work=/tmp/work
python=$(command -v python3)

mkdir -p "$work/projects"
cp -RP /tracer/benchmark/. "$work/"
cp -RP "/inputs/macro-benchmark/projects/$name" "$work/projects/$name"

"$python" -I -c 'import platform; print("python:", platform.python_version(), platform.machine(), platform.libc_ver()[0])'
"$python" -I -B /tracer/evaluation/macro-benchmark/trace.py "$name" \
    --benchmark-dir "$work" --locate
exec "$python" -I -B /tracer/evaluation/macro-benchmark/trace.py "$name" \
    --python "$python" --benchmark-dir "$work" --output /out/trace.json
