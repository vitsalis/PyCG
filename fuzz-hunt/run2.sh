#!/bin/sh
TREE=/home/vitbot/pycg/tmp-archive/engine-fixes-2/fuzz-tree
F=/home/vitbot/pycg/tmp-archive/engine-fixes-2/fuzz
/home/vitbot/pycg/perf-study/scripts/waitturn.sh
exec docker run --rm --name "fuzz-engine-fixes-2-$1" --label owner=engine-fixes-2 -m 2g --memory-swap 2g --network none --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -v "${TREE}:${TREE}:ro" -v "${F}:${F}" \
  pycg-ci-uv python3 -I "$F/driver.py" "$TREE" "$F/$1.jsonl" "$2" "$3" "$4" "$5"
