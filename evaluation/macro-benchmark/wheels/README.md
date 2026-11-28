# Wheels built here

A test environment installs wheels only, each pinned by its SHA-256. A
dependency that PyPI has no wheel of is built here once from its pinned
sdist and committed beside this file.

## odfpy 1.4.1 (for tablib, batch 8)

| | |
|---|---|
| Input | `odfpy-1.4.1.tar.gz` from PyPI, SHA-256 `db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec` |
| Scan | Scans A and B of batch 8 (Claude Fable 5.2): safe to build with restrictions; no code of the package runs at build time |
| Build | 2026-11-24, in a sealed container (no network, read-only root, no capability) with setuptools 83.0.0 alone (`build-requirements.txt`); three builds gave the same bytes |
| Output | `odfpy-1.4.1-py2.py3-none-any.whl`, 160,717 bytes, SHA-256 `19548df9de7970e8cb6b120eb0de3232561de6c876b2642a91e1b9c88c2af2f8` |
| Record | The build log (`.build.log`) and the check report against the sdist (`.check.json`) beside the wheel |
| Pinned | `test-environments/tablib.txt`, as `odfpy==1.4.1` by that hash |
