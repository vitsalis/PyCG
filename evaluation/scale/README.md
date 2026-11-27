# Scale set

Twenty large packages on which PyCG's time and peak memory are measured.
They have no ground truth and are not scored or gated, and a change of them
does not change the digest of the benchmark.

`projects.toml` pins each package by the URL and the SHA-256 of one
archive: a wheel of PyPI or the archive of a commit that GitHub serves.
Only the Python sources and the licence files of an archive are unpacked.
The entry points are every `.py` file of the package's analysed packages.

A run of one package gives:

| Value | Meaning |
|---|---|
| outcome | `finished`; `killed by the cap` when the analysis passed the memory cap (4 GiB unless the run sets another) and the runner stopped it; a kill from outside the runner (below); otherwise the runner's status (`timeout`, `crash`) |
| seconds | The time of the analysis |
| peak MiB | The peak resident set size of the analysis; for a run that did not finish, the largest of the runner's samples |
| MiB available at the start | The memory that the machine had available (`MemAvailable` of `/proc/meminfo`, the machine's in a container) when the run started; a container larger than it can be killed by the machine's OOM killer |
| graph SHA-256 | The SHA-256 of the call graph of a finished run; two runs with the same SHA-256 gave byte-identical graphs |

The analysis runs under the cap, in a container with 512 MiB more, so that
the analysis is stopped at the cap and the run survives to record it. The
headroom covers twice the largest growth of the analysis between two
samples of its memory, 203 MiB in 0.25 s on scikit-learn (numpy: 61 MiB),
and the memory of the measuring script.

A SIGKILL that the runner did not send is not the cap. The container's
memory cgroup counts the OOM kills of its processes (`oom_kill` of
`memory.events`) and the times it reached its own limit (`oom`); the
counters before and after the run name the kill:

| Outcome | Counters | Cause |
|---|---|---|
| `killed: the container ran out of memory` | `oom` rose | The container reached its own limit, the cap and the headroom: the analysis grew faster than the runner samples it, or the runner needed more |
| `killed: the machine ran out of memory` | only `oom_kill` rose | The kernel's OOM killer of the whole machine, which kills the largest process: the container's limit is more than the machine has free |
| `killed by SIGKILL` | neither, or no cgroup | Another process |

Such a run is not a measurement: `compare`, and so `make eval-scale`,
refuse it and say which run to repeat on a machine with the container's
memory free.

## Packages

| Package | Pin | Analysed packages | Licence |
|---|---|---|---|
| pydantic | 2.14.2, pure wheel | `pydantic` | MIT |
| numpy | 2.5.4, platform wheel | `numpy` | BSD-3-Clause |
| pandas | 3.1.0, platform wheel | `pandas` | BSD-3-Clause |
| fsspec | 2026.9.0, pure wheel | `fsspec` | BSD-3-Clause |
| rich | 15.0.0, pure wheel | `rich` | MIT |
| pip | 26.2.2, pure wheel | `pip` | MIT |
| sqlalchemy | 2.1.6, pure wheel | `sqlalchemy` | MIT |
| pyparsing | 3.3.3, pure wheel | `pyparsing` | MIT |
| scipy | 1.18.1, platform wheel | `scipy` | BSD-3-Clause |
| openai | 3.42.1, pure wheel | `openai` | Apache-2.0 |
| dask | commit 08d1856d3e | `dask` | BSD-3-Clause |
| matplotlib | commit 58b6a0663e | `matplotlib`, `mpl_toolkits` (in `lib/`) | Matplotlib License (PSF-based) |
| scikit-learn | commit b39ab8987b | `sklearn` | BSD-3-Clause |
| sphinx | commit eaebbec4d1 | `sphinx` | BSD-2-Clause |
| sympy | commit bfdb8d51c1 | `sympy` | BSD-3-Clause |
| xarray | commit 60bc816cd1 | `xarray` | Apache-2.0 |
| cerberus | commit 8765b31744 | `cerberus` | ISC |
| python-future | commit af1db970b0 | `_dummy_thread`, `_markupbase`, `_thread`, `builtins`, `copyreg`, `future`, `html`, `http`, `libfuturize`, `libpasteurize`, `past`, `queue`, `reprlib`, `socketserver`, `tkinter`, `winreg`, `xmlrpc` (in `src/`) | MIT |
| graphene | commit 52143473ef | `graphene` | MIT |
| elasticsearch-dsl-py | commit 5874ff6bd5 | `elasticsearch_dsl` | Apache-2.0 |

The licence of each package is read from the licence files of its pinned
archive. The platform wheels of numpy and scipy also bundle compiled
libraries under other licences (the GCC runtime under GPL-3.0-or-later
with the GCC runtime library exception, libquadmath under LGPL-2.1); those
libraries are not unpacked.
