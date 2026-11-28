# Scale set

Twenty large packages on which PyCG's time and peak memory are measured,
and whether it finishes under a memory cap.

The benchmarks' packages are small enough to analyse in seconds, so they
cannot show how PyCG does on packages of this size.

| | |
|---|---|
| Ground truth | None; the set is not scored or gated |
| Digest of the benchmark | Not changed by a change of the set |
| Pin | The URL and the SHA-256 of one archive: a wheel of PyPI or the archive of a commit that GitHub serves |
| Entry points | Every `.py` file of the package's analysed packages |

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
archive.

The platform wheels of numpy and scipy also bundle compiled libraries under
other licences (the GCC runtime under GPL-3.0-or-later with the GCC runtime
library exception, libquadmath under LGPL-2.1); those libraries are not
unpacked.

## Results

| Parameter | Value |
|---|---|
| Engine | `pycg` at commit c7fc8fb3f9 with the default cap of 1,000 objects per node |
| Runs | One package at a time |
| Memory cap | 13 GiB |
| Machine | 4-core Intel Xeon at 2.3 GHz |

| Package | Outcome | Seconds | Peak MiB |
|---|---|---|---|
| pydantic | finished | 2.3 | 192 |
| numpy | finished | 8.7 | 494 |
| pandas | finished | 231.9 | 6,537 |
| fsspec | finished | 6.3 | 215 |
| rich | finished | 1.3 | 120 |
| pip | finished | 8.8 | 404 |
| sqlalchemy | finished | 25.4 | 1,165 |
| pyparsing | finished | 1.1 | 120 |
| scipy | finished | 34.0 | 1,168 |
| openai | finished | 7.0 | 313 |
| dask | finished | 8.5 | 641 |
| matplotlib | finished | 27.1 | 813 |
| scikit-learn | finished | 31.6 | 701 |
| sphinx | finished | 7.4 | 495 |
| sympy | finished | 161.1 | 4,720 |
| xarray | finished | 10.1 | 596 |
| cerberus | finished | 1.0 | 174 |
| python-future | finished | 4.9 | 325 |
| graphene | finished | 0.5 | 77 |
| elasticsearch-dsl-py | finished | 0.4 | 50 |

All 20 packages finish, each in under 4 minutes and 7 GiB.
