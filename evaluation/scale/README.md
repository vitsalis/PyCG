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

## Results

`pycg` at commit 56611d8dc3, one package at a time with
`make eval-scale NAME=<package> SCALE_MEMORY_MIB=12288`, on an Intel(R)
Xeon(R) Processor at 2,700 MHz with 4 cores. The document SHA-256 is that
of the document that `pycg` writes.

| Package | Outcome | Seconds | Peak MiB | Graph SHA-256 | Document SHA-256 | MiB available at the start |
|---|---|---|---|---|---|---|
| pydantic | finished | 12.4 | 636 | `0788d5985bc257e10a153398eaf5b5f60594f9c907e76ef3d07d73e68806353f` | `d4d3c17021319abfb02bfeb6a69dc51f335429dc209429a1bf8602140cad364a` | 15,336 |
| numpy | finished | 229.5 | 1,468 | `57c222ec8d75e8b06ccad7d14558788861b5ffd058dbf3ff3cb9e23ffdf83366` | `448c91b96e7c55d9751e2fab79a562c815c2d3776123632a3c72ff9f8aef256f` | 15,230 |
| pandas | finished | 228.4 | 8,072 | `35a156c328742e73596f2f3c415c956aa9b1ae903bc815018f37f48a2981f9de` | `1982cc9b482121f9d6c8c60259f691763dc64a2089b702b971ef6aa327cba876` | 15,257 |
| fsspec | finished | 5.0 | 218 | `ea47bd08682f1e495f9ccd99134ab7b0ff894df6a006604ccb57e958464669a4` | `4bbad8c7c1ac3ec7d88f9bf9ffec128fc44db74993743bd6fe0984054cd2a049` | 15,038 |
| rich | finished | 1.9 | 211 | `3e36492b53fc46407a27561b1a25f0972937c7488b2199af38d6509c7c3cf39c` | `ca81de5e4474df00b8bba9108040ee1e6b094f1b297100443284fd4dbf9a304b` | 15,231 |
| pip | finished | 29.1 | 1,069 | `1b8fc6b758bfc5c5f9aac525a830286ee50c81229835efeae7e2f4ea5dda807d` | `9f6963a4c89341d491170b28a201ccc1b0e291b6adbdfc7de768d008eb97c6f5` | 15,223 |
| sqlalchemy | finished | 69.9 | 5,660 | `7e547018ec6f5edc44a8f0beb134eac2092a5c3c543160b38ee78a3a20128020` | `5ad5c7958cc8c86f5b2aa4a2c46ded438b837a02f703c1e8b2a7b89610aa7b50` | 15,186 |
| pyparsing | finished | 3.4 | 224 | `7734dd1965c69598abf1c0c9e8ba9f90cd9c9cc2717ae5b5f7e750e430a09427` | `8ebf55410e8fd190bf7497b46a325248e9bbf251174980ca94b0aa820e987a7d` | 14,999 |
| scipy | finished | 71.2 | 2,298 | `6c6a29457d283e00f14ace401960c4866d4e9a1e8395b25c3639ae11c2d29222` | `317b9c8cb3de58d89900bd64ffa2376f1daff20eb8f8036ccc16d0407402e0a8` | 15,073 |
| openai | finished | 27.3 | 2,050 | `6f591d617ea3f8e358c61af4c82cb12fd07b8f898327e7882fdc80dbb8ecde8f` | `7d0644ed11cfecfb058bf2b33f79b9295cd3639e1b76516992da16f0db99605d` | 14,786 |
| dask | finished | 23.5 | 1,714 | `59e78cad7db5b690c9c74b3d3ff137f6bced8115e519d5da999d349e7c5b33db` | `de1bbd89070753561a417c47dc554b2403b54a7e632d8d22e3f5c2285de9ccfa` | 15,056 |
| matplotlib | finished | 31.7 | 1,292 | `49808c5c0ea44cfb25ebe5a5706a796694a4fc26dca84831a0e15665942a5993` | `3955877e37a71e18d313473cb06f3927fc43e3360bb5085c4bb5d579379e31b5` | 15,161 |
| scikit-learn | finished | 151.5 | 5,056 | `86d06c93d3c004d4ffe8584dd234a73f4032629345b803451ad389ed6e4a72c5` | `da00ad0712d48f327bf10290f3f64dab0370eceeea53cfe505cf73923ef9663a` | 14,999 |
| sphinx | finished | 6.7 | 513 | `6ce342d2dd8a67ec7b2cc0733905a31cad9adb7520b3010afd15a5c4d9510f20` | `0b89bb0c7e158c9a98af11033a187a41e8f2715c8359c444f40d92b50f84597b` | 15,076 |
| sympy | crash: `internal error at crates/analysis/src/engine/arguments.rs:247:50: an index fits i64` | 142.9 | 4,256 | – | – | 14,873 |
| xarray | finished | 28.2 | 1,991 | `a27b3dc3914f56c4a8c89691fc00102b11c3f202d33b6af882555b011b9a9c60` | `0086314d3c787c6fbad5b07ecc81d339511e4e7cf50f012cf5f4140a0438efc6` | 15,053 |
| cerberus | finished | 12.6 | 422 | `909ceb867d2cbd183aca07163a6440e46b36feeee94545b746214796c589262d` | `8d828c554e2c1b997582131d6c2bdf85cf1f8983707b205fad7816e6b3c9146c` | 15,160 |
| python-future | finished | 35.5 | 979 | `fb3196bebc7c14b46f122230940072d71d2e49af4fbc552a86d1804a37c1aa48` | `d4ff963adc87f5c39d64ba674c4528ebad89ddfe113de49d3881701144e049a0` | 15,254 |
| graphene | finished | 0.8 | 171 | `1af6074fdbe736f087fda8f051f771105038f71ab5b3b3c7adedcdaca06a87d3` | `3ced3f48c17d0a92ad694802e773a1517efd606913be4b9c9b54d10a1bc3fe65` | 15,279 |
| elasticsearch-dsl-py | finished | 5.2 | 410 | `be9ae89413287e4db40fa151c9cc3307a0004abaed7e57add5fefed2b2449a68` | `fac8bf13804d6b3b4e050c2791e7dfa3e156d80bbe70cb5ca14929ae307ada4a` | 15,227 |
