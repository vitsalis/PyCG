# Cloud environment smoke test

Date: 2026-11-26. Commit under test: `main` at `0f1b0699a4`. Machine: 4 CPUs,
16 087 MiB RAM, no swap, kernel 6.18.44, running as root.

## Summary

| Step | Result |
|---|---|
| 1. Tools | Partly. All tools present. `check-tools` exits 1 (only the Python document libraries are missing). The Docker daemon was not running until I started `dockerd` by hand. |
| 2. Pythons and Rust | Partly. Rust works and crates.io is reachable. **Python versions are wrong:** 3.14.6 instead of 3.14.10, and 3.15.0b4 (a beta) instead of 3.15.2. |
| 3. Docker limits | Pass. The OOM kill gives exit 137, `--network none` blocks network access, and the hardened flags work. |
| 4. `make check` / `make check FULL=1` | Pass, in 2 s and 170 s. |
| 5. `make eval` | **Fail after 12 s.** The first image build cannot run `apt-get`, because the containers have no route out and the network policy blocks `deb.debian.org`. |
| 6. Branch, commit, draft PR | See the end of this report. |

## 1. Tools

| Command | Exit | Time | Key output |
|---|---|---|---|
| `check-tools` | 1 | 11.9 s | Every tool ✅ except `❌ python3.13 document libraries: cannot import docx markitdown openpyxl pandas pdfplumber pptx pypdf pypdfium2 reportlab`, then "Tool validation failed". PyCG does not need these libraries. |
| `python3 --version` | 0 | <0.1 s | Python 3.13.18 |
| `uv --version` | 0 | <0.1 s | uv 0.11.32. Every uv call warns that `UV_NATIVE_TLS` is deprecated (`UV_SYSTEM_CERTS` replaces it). |
| `docker version` | 1 | <0.1 s | Client 29.9.3. `failed to connect to the docker API at unix:///var/run/docker.sock`: the daemon was not running. |
| `nohup dockerd &` (by hand) | 0 | ~1 s | Server 29.9.3, containerd v2.4.2, overlayfs, cgroupfs driver, **cgroup v1**, 4 CPUs, 15.71 GiB |
| `rustc --version` | 0 | <0.1 s | rustc 1.100.0 (0ef1bc386 2026-11-09) |
| `cargo --version` | 0 | <0.1 s | cargo 1.100.0 (3acc79c0c 2026-11-05) |
| `gh --version` | 0 | <0.1 s | gh 2.89.0 (2026-03-26) |
| `nproc` | 0 | <0.1 s | 4 |
| `free -m` | 0 | <0.1 s | total 16087, used 538, available 15548, swap 0 |

## 2. Pythons and Rust

`uv python list --only-installed` (0.5 s):

| Version | Path | Expected |
|---|---|---|
| cpython-3.15.0b4 | `/root/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu` | **3.15.2: wrong, this is a beta** |
| cpython-3.14.6 | `/root/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu` | **3.14.10: wrong** |
| cpython-3.13.18 | `/usr/local/bin`, `/usr/bin` (system) | n/a |
| cpython-3.13.14 | `/root/.local/share/uv/python/...` | n/a |
| cpython-3.12.13 | `/root/.local/share/uv/python/...` | n/a |
| cpython-3.12.3 | `/usr/bin/python3.12` | n/a |
| cpython-3.11.18 | `/usr/bin/python3.11` | n/a |

`make check` created `.venv` with "Using CPython 3.14.6". So the local tests
ran on 3.14.6, not on the 3.14.10 that the `python:3.14-slim` image ships
(I checked: `docker run --rm python:3.14-slim python -V` prints Python 3.14.10).

Rust:

- `which rustc cargo rustup` prints `/root/.cargo/bin/{rustc,cargo,rustup}`, and
  `which -a` finds no other rustc or cargo on PATH. `rustc` is a symlink to
  `rustup`. **Confirmed: rustup's toolchain is the one on PATH.**
- `rustup show`: one toolchain, `stable-x86_64-unknown-linux-gnu`, active and
  the default. rustup home is `/root/.rustup`.
- `cargo new --bin /tmp/hello && cargo run --manifest-path /tmp/hello/Cargo.toml`:
  exit 0, under 1 s, `Hello, world!`.
- A crate that depends on `serde_json` (`cargo add serde_json`, then
  `cargo run`): exit 0, 3 s. It printed "Updating crates.io index",
  "Locking 11 packages", compiled, and printed `2`. **crates.io is reachable.**

## 3. Docker limits

| Command | Exit | Time | Result |
|---|---|---|---|
| `docker pull -q python:3.14-slim` | 0 | 4 s | Docker Hub pulls work, because the daemon inherits the proxy. |
| `docker run --rm --memory 512m --memory-swap 512m python:3.14-slim python -c "b = bytearray(1024**3)"` | **137** | 0.6 s | Killed as expected. The cgroup v1 `memory.limit_in_bytes` inside reads 536870912. |
| `docker run --rm --network none python:3.14-slim python -c "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=5)"` | 1 | 0.5 s | `URLError: [Errno -3] Temporary failure in name resolution`: the request failed as expected. |
| `docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 python:3.14-slim sh -c 'id; echo hi > /tmp/f && cat /tmp/f; grep CapEff /proc/self/status; grep NoNewPrivs /proc/self/status'` | 0 | <1 s | `uid=1000 gid=1000`, `/tmp` writable (`hi`), `CapEff: 0000000000000000`, `NoNewPrivs: 1`. A write to `/x` fails with `Errno 30 Read-only file system`. |

## 4. The repository's checks

| Command | Exit | Wall time | Output |
|---|---|---|---|
| `make check` | 0 | 2 s (first run, venv included) | `uv` built the venv (3.14.6, 9 packages); `lint pass 0.8 s`. With no diff against `origin/main`, only lint runs. |
| `make check FULL=1` | 0 | 170 s | `lint pass 0.8 s`, `test pass 168.9 s` |

Note: `make check FULL=1` runs `make lint` and `make test` in the local `uv`
environment (`tools/check.py --full`). It does not build or use a container.

## 5. The evaluation: `make eval`

Command: `make eval`, run in the background, with `free -m` sampled every 30 s.

- **Result: fails at once.** Exit 2 after 12 s of wall time, in the target
  `eval-inputs`, at the first build:
  `docker build --target macro -t pycg-eval-macro -f evaluation/container/Dockerfile.inputs .`
- The base image (`python:3.14-slim@sha256:9aaa4740…`) resolves and loads.
- The failing step is `Dockerfile.inputs:25`, in the stage `network`:
  `RUN apt-get update && apt-get install --yes --no-install-recommends git ca-certificates …`:
  ```
  Err:1 http://deb.debian.org/debian trixie InRelease
    Could not resolve 'deb.debian.org'
  E: Unable to locate package git
  ERROR: failed to build: ... did not complete successfully: exit code: 100
  make: *** [Makefile:85: eval-inputs] Error 1
  ```
- Nothing was measured: no micro or macro analysis ran, and the run printed no summary table.
- Peak VM memory: 643 MiB used, 15 443 MiB available (two samples, at 07:11:12
  and 07:11:42). The run was too short for this number to mean anything.

### Why

The session's only route out is an HTTPS proxy on `127.0.0.1:44285`, which
re-signs TLS with its own CA. Containers on Docker's default bridge network
cannot reach it and have no DNS, so a build step has no network at all.
Follow-up probes (they changed nothing):

| Probe from a `--network host` container, with `https_proxy` and the proxy CA | Result |
|---|---|
| `https://deb.debian.org/debian/dists/trixie/InRelease` | **403 from the proxy: "no rule or network setting allows this host"** |
| `http://deb.debian.org/...` (plain HTTP, no proxy) | Name not resolved. The proxy serves HTTPS only. |
| `https://github.com/<repo>.git/info/refs` (56 of the pins are on github.com) | 200, reachable |
| `https://files.pythonhosted.org/` (5 sdist pins) | 404 on the bare root, so the host is reachable |

### What would let `make eval` run here

1. The environment's network policy must allow `deb.debian.org` (Debian's apt
   mirror is not among the package registries it allows by default). Another
   way: an image that already has `git` and `ca-certificates`, so the build
   does not need apt.
2. The build steps that fetch (apt, and `fetch.py`'s git and sdist downloads)
   need `--network host`, `https_proxy`, and the proxy CA installed in the
   image. apt would also need `https://` sources. These are changes to the
   build or the Makefile, which this test does not make. They would also run
   the untrusted fetch outside Docker's network isolation, so they need a
   decision first.
3. Without both, the 4 GiB macro containers and the micro run were not
   reached. Their behaviour in this environment is still untested.

## 6. Branch and pull request

- Branch `vitsalis/cloud-smoke-test`, from `main` at `0f1b0699a4`, holds one
  commit that adds only this file.
- The draft pull request is opened with `gh api repos/vitsalis/PyCG/pulls … -F draft=true`.
  Its number and outcome are in the session's final report.
