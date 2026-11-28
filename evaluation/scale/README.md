# Scale set

Twenty large packages on which PyCG's time and peak memory are measured,
and whether it finishes under a memory cap. The benchmarks' packages are
small enough to analyse in seconds, so they cannot show how PyCG does on
packages of this size. The set has no ground truth and is not scored or
gated, and a change of it does not change the digest of the benchmark.

Each package is pinned by the URL and the SHA-256 of one archive: a wheel
of PyPI or the archive of a commit that GitHub serves. The entry points are
every `.py` file of the package's analysed packages.

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

`pycg` at commit 56611d8dc3, one package at a time under a memory cap of
12 GiB, on a 4-core Intel Xeon at 2.7 GHz:

| Package | Outcome | Seconds | Peak MiB |
|---|---|---|---|
| pydantic | finished | 12.4 | 636 |
| numpy | finished | 229.5 | 1,468 |
| pandas | finished | 228.4 | 8,072 |
| fsspec | finished | 5.0 | 218 |
| rich | finished | 1.9 | 211 |
| pip | finished | 29.1 | 1,069 |
| sqlalchemy | finished | 69.9 | 5,660 |
| pyparsing | finished | 3.4 | 224 |
| scipy | finished | 71.2 | 2,298 |
| openai | finished | 27.3 | 2,050 |
| dask | finished | 23.5 | 1,714 |
| matplotlib | finished | 31.7 | 1,292 |
| scikit-learn | finished | 151.5 | 5,056 |
| sphinx | finished | 6.7 | 513 |
| sympy | crash (internal assertion) | 142.9 | 4,256 |
| xarray | finished | 28.2 | 1,991 |
| cerberus | finished | 12.6 | 422 |
| python-future | finished | 35.5 | 979 |
| graphene | finished | 0.8 | 171 |
| elasticsearch-dsl-py | finished | 5.2 | 410 |

19 of the 20 packages finish; sympy stops on an internal assertion, a
defect of the engine.
