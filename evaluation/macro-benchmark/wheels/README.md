# Wheels built here

A test environment installs wheels only, each by its SHA-256
(`test-environments/<name>.txt`, `pip install --require-hashes --only-binary :all:
--no-deps`). A dependency that PyPI has no wheel of is built here once, from
its pinned sdist, in a container, and the built wheel is committed beside
this file and pinned by its own SHA-256 like any other. The trace image gets
this directory as the build context `wheels` and pip's `--find-links`
(`evaluation/container/Dockerfile.trace`, `trace.sh`); the image tag hashes
its files (`trace_helper.py image-tag`), so a new or changed file here gives
every project a new image tag.

## odfpy 1.4.1 (for tablib, batch 8)

odfpy has no wheel in any release on PyPI (1.4.1, 2020-01-18, is an sdist
and a Python 2.7 egg); tablib's tests import it. The maintainer's decision
(2026-11-24): build its wheel from the pinned sdist in a container, after a
security scan of that sdist (scans A and B of batch 8: safe to build with
restrictions, which the recipe follows). The wheel was built and checked
in the earlier evaluation repository, by the scripts that this section
names (`Dockerfile.wheel`, `build_wheel.sh`, `build_wheel_inside.sh`,
`wheel_check.py` and their tests); they are not part of this repository,
and the build log and the check report beside the wheel are the record.

- **Input**: `odfpy-1.4.1.tar.gz`, SHA-256
  `db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec`,
  downloaded from PyPI's file host in a container and checked against that
  hash (for the scans: unpacked by `evaluation/container/fetch.py`'s
  `fetch_sdist`, which checks it too). Its `setup.py` (119 lines) imports
  `platform` and `setuptools` and calls `setup()` with literals; no code of
  the package `odf` runs at build time.
- **Build environment**: `evaluation/container/Dockerfile.wheel`, the base
  image of the trace images with setuptools 83.0.0 alone (the release on or
  before tablib's date, 2026-07-31), by hash from `build-requirements.txt`;
  no setuptools plugin, no `wheel` distribution. setuptools never enters a
  trace image (its `distutils-precedence.pth` would run at every start).
- **Build**: `evaluation/container/build_wheel.sh ARCHIVE SHA256 EPOCH
  OUT_DIR`. The script refuses a `PYTHON_IMAGE` without a digest, an
  archive name other than `NAME-VERSION.tar.gz` and an archive of another
  SHA-256, before anything runs; then a container without network,
  read-only root, no capability, user 10001, the archive and
  `build_wheel_inside.sh` mounted read-only, and as the only writable
  mount an output directory of the script's temporary directory (mode
  0777, as `trace.sh`'s; the wheel is copied from it to `OUT_DIR`, so the
  build writes on native Docker under any uid of the caller; review
  batch8-r2, N2); inside, it lists the builder's
  site-packages, unpacks the archive with tarfile's "data" filter onto a
  tmpfs, and runs `pip wheel --no-deps --no-build-isolation --no-index` in
  an environment of PATH, an empty HOME and TMPDIR,
  `PIP_CONFIG_FILE=/dev/null` and `SOURCE_DATE_EPOCH=1579366500`
  (2020-01-18 16:55 UTC, the upload of the sdist). Python 3.14 (the trace
  images' base, `python:3.14-slim@sha256:9aaa4740…`). `tests/
  test_build_wheel.py` holds these flags.
- **Builds**: on 2026-11-24, twice with the first version of the script
  (the unpacked sdist as input), into two empty directories, and once more
  with this version (the archive as input), after review batch8-r1: the
  same bytes each time. The log of the third build is
  `odfpy-1.4.1-py2.py3-none-any.whl.build.log`: the builder's
  site-packages are pip 26.2.2 and setuptools 83.0.0, and one `.pth` file,
  setuptools' `distutils-precedence.pth` (scan B, check 1).
- **Output**: `odfpy-1.4.1-py2.py3-none-any.whl`, 160,717 bytes, SHA-256
  `19548df9de7970e8cb6b120eb0de3232561de6c876b2642a91e1b9c88c2af2f8`.
- **Check** (`evaluation/container/wheel_check.py` against the archive of
  the pinned SHA-256, with `--package odf --requires defusedxml
  --data-prefix share/man/man1/` and the eleven scripts by name; the report
  `odfpy-1.4.1-py2.py3-none-any.whl.check.json`, with the SHA-256 of each
  member and of the sdist): 60 members, no problem: the 34 modules
  `odf/*.py`, each byte for byte equal to the sdist's; the 11 scripts of
  `odfpy-1.4.1.data/scripts/`, each equal to the sdist's after the first
  line (which the build rewrites); the 11 man pages of
  `odfpy-1.4.1.data/data/share/man/man1/`, each equal to the sdist's;
  `METADATA`, `WHEEL`, `RECORD` and `top_level.txt` (`odf`);
  `Requires-Dist: defusedxml` alone. No `.pth` file, no entry point, no
  compiled module, no other top-level name, no other script or data file,
  no member twice.
  `tests/test_wheel_check.py` derives the members and their hashes from the
  committed wheel again and compares them with the report.
- **Pinned** in `test-environments/tablib.txt` as `odfpy==1.4.1` by that hash,
  with `defusedxml==0.7.1` (PyPI's wheel).
