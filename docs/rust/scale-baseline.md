# Scale baseline of the Python engine

`make eval-scale NAME=<package> SCALE_MEMORY_MIB=12288`, one package at a time;
D6 is `dumps(CallGraphGenerator.document())`, run in the same sandbox after it.

| Package | Outcome | Seconds | Peak MiB | Graph SHA-256 | D6 SHA-256 | MiB available at the start |
|---|---|---|---|---|---|---|
| pydantic | finished | 69.7 | 1,112 | `0788d5985bc257e10a153398eaf5b5f60594f9c907e76ef3d07d73e68806353f` | `e62dc63780d23b3234bf04d1bf3fa8ea068ce42644fb84ffd86a760043966a6a` | 15,415 |
| numpy | finished | 618.6 | 1,987 | `57c222ec8d75e8b06ccad7d14558788861b5ffd058dbf3ff3cb9e23ffdf83366` | `24640df7e96f774b7f39cd51019166684f345ba88afa09e622ed0a161bfd3ed9` | 15,421 |
| pandas | finished | 326.1 | 10,688 | `35a156c328742e73596f2f3c415c956aa9b1ae903bc815018f37f48a2981f9de` | `c6a332196ca0ed5cfef66f7df33da151e6c197c85f750ed1c1680a7ba9991497` | 15,424 |
| fsspec | finished | 32.2 | 372 | `ea47bd08682f1e495f9ccd99134ab7b0ff894df6a006604ccb57e958464669a4` | `9237ae0b0a860cb75b97f256096a0af2104cf438f56927cfcc3d5a862959edb7` | 15,372 |
| rich | finished | 17.9 | 373 | `3e36492b53fc46407a27561b1a25f0972937c7488b2199af38d6509c7c3cf39c` | `497f1b1699074f69cd2c5b8f623b4bb7e9a1d66abc9cdbfd51a0f390511fbf41` | 15,362 |
| pip | finished | 158.8 | 1,984 | `1b8fc6b758bfc5c5f9aac525a830286ee50c81229835efeae7e2f4ea5dda807d` | `e924ac133ecefacf06aee0c142ff77c8e3eefca78eee21b872bd5e11eab217f5` | 15,329 |
| sqlalchemy | finished | 450.1 | 9,090 | `7e547018ec6f5edc44a8f0beb134eac2092a5c3c543160b38ee78a3a20128020` | `b64134d27d5006152b9cb7c3335a094040327e30396e1879b77160a3c837f266` | 15,368 |
| pyparsing | finished | 17.6 | 382 | `7734dd1965c69598abf1c0c9e8ba9f90cd9c9cc2717ae5b5f7e750e430a09427` | `a0de26db41dc9977d91b7fec8c74e5f19ce13a2c0f5c30bf81a2b7213ccb8420` | 15,366 |
| scipy | finished | 220.5 | 3,811 | `6c6a29457d283e00f14ace401960c4866d4e9a1e8395b25c3639ae11c2d29222` | `9176e8075d99abe759aa9e4226d6f575d498743f3e430a3c27781282e32ca1ca` | 15,367 |
| openai | finished | 204.5 | 4,644 | `6f591d617ea3f8e358c61af4c82cb12fd07b8f898327e7882fdc80dbb8ecde8f` | `841fbfe24e811507a299cea0ef3d7361aa0b7978da41c66cb4cb6c600d9cf2ec` | 15,363 |
| dask | finished | 123.8 | 3,102 | `59e78cad7db5b690c9c74b3d3ff137f6bced8115e519d5da999d349e7c5b33db` | `8146ba7798b16cdee3dabde39099264d6575e628d3c34a2d9a2b1c66eed5666e` | 15,277 |
| matplotlib | finished | 89.8 | 1,893 | `49808c5c0ea44cfb25ebe5a5706a796694a4fc26dca84831a0e15665942a5993` | `7fb90f33317f441c6c332fd8fd098cb3b42c5e3fa9867ad793793fd3833126ad` | 15,348 |
| scikit-learn | finished | 827.3 | 10,268 | `86d06c93d3c004d4ffe8584dd234a73f4032629345b803451ad389ed6e4a72c5` | `4766ef74f4f5d2e9a43de7c877c96e462ef7a9688100f4f11f764f6d66342694` | 15,345 |
| sphinx | finished | 32.9 | 683 | `6ce342d2dd8a67ec7b2cc0733905a31cad9adb7520b3010afd15a5c4d9510f20` | `8e22a63e8bd2f305be9a35202dca61a1847ec2eb07bc8a08269bd125ec02746f` | 15,240 |
| sympy | killed by the cap at 12,288 MiB | – | 12,358 | – | – | 15,363 |
| xarray | finished | 223.3 | 3,335 | `a27b3dc3914f56c4a8c89691fc00102b11c3f202d33b6af882555b011b9a9c60` | `df8233b9833578e49387fdcb35189aea430415439f8051cdd0691721f723ce81` | 15,293 |
| cerberus | finished | 71.3 | 699 | `909ceb867d2cbd183aca07163a6440e46b36feeee94545b746214796c589262d` | `a3e09f8571922bdaeb25864ae0d5dc460981f8bff5fecfbf5ce527df96863b80` | 15,366 |
| python-future | finished | 233.6 | 1,590 | `fb3196bebc7c14b46f122230940072d71d2e49af4fbc552a86d1804a37c1aa48` | `aede8d2734fa5904223707c439742fbc57dd381220f8e229ab248c2ae816d96b` | 15,356 |
| graphene | finished | 10.3 | 378 | `1af6074fdbe736f087fda8f051f771105038f71ab5b3b3c7adedcdaca06a87d3` | `3dd2a5390a436f3cb46b605283962136a74459489e3d63e6d4fb328d63d5f020` | 15,361 |
| elasticsearch-dsl-py | finished | 47.2 | 667 | `be9ae89413287e4db40fa151c9cc3307a0004abaed7e57add5fefed2b2449a68` | `033fadd273dd18c24497fb147d9120bcff7ea67afafc34bf2863e489dfc26c1a` | 15,342 |

Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores; commit 7e58d09d26 of
base/rust-rewrite.

Rust `pycg` at commit 56611d8dc3 of base/rust-rewrite, by `make eval-scale-rust
NAME=<package> SCALE_MEMORY_MIB=12288`; its document is D6 and a final newline.

| Package | Outcome | Seconds | Peak MiB | Graph SHA-256 | Document SHA-256 | MiB available at the start | Graph against Python | Document against D6 | Seconds, Rust/Python | Peak MiB, Rust/Python |
|---|---|---|---|---|---|---|---|---|---|---|
| pydantic | finished | 12.4 | 636 | `0788d5985bc257e10a153398eaf5b5f60594f9c907e76ef3d07d73e68806353f` | `d4d3c17021319abfb02bfeb6a69dc51f335429dc209429a1bf8602140cad364a` | 15,336 | identical | identical | 0.179 | 0.57 |
| numpy | finished | 229.5 | 1,468 | `57c222ec8d75e8b06ccad7d14558788861b5ffd058dbf3ff3cb9e23ffdf83366` | `448c91b96e7c55d9751e2fab79a562c815c2d3776123632a3c72ff9f8aef256f` | 15,230 | identical | identical | 0.371 | 0.74 |
| pandas | finished | 228.4 | 8,072 | `35a156c328742e73596f2f3c415c956aa9b1ae903bc815018f37f48a2981f9de` | `1982cc9b482121f9d6c8c60259f691763dc64a2089b702b971ef6aa327cba876` | 15,257 | identical | identical | 0.700 | 0.76 |
| fsspec | finished | 5.0 | 218 | `ea47bd08682f1e495f9ccd99134ab7b0ff894df6a006604ccb57e958464669a4` | `4bbad8c7c1ac3ec7d88f9bf9ffec128fc44db74993743bd6fe0984054cd2a049` | 15,038 | identical | identical | 0.156 | 0.59 |
| rich | finished | 1.9 | 211 | `3e36492b53fc46407a27561b1a25f0972937c7488b2199af38d6509c7c3cf39c` | `ca81de5e4474df00b8bba9108040ee1e6b094f1b297100443284fd4dbf9a304b` | 15,231 | identical | identical | 0.106 | 0.57 |
| pip | finished | 29.1 | 1,069 | `1b8fc6b758bfc5c5f9aac525a830286ee50c81229835efeae7e2f4ea5dda807d` | `9f6963a4c89341d491170b28a201ccc1b0e291b6adbdfc7de768d008eb97c6f5` | 15,223 | identical | identical | 0.184 | 0.54 |
| sqlalchemy | finished | 69.9 | 5,660 | `7e547018ec6f5edc44a8f0beb134eac2092a5c3c543160b38ee78a3a20128020` | `5ad5c7958cc8c86f5b2aa4a2c46ded438b837a02f703c1e8b2a7b89610aa7b50` | 15,186 | identical | identical | 0.155 | 0.62 |
| pyparsing | finished | 3.4 | 224 | `7734dd1965c69598abf1c0c9e8ba9f90cd9c9cc2717ae5b5f7e750e430a09427` | `8ebf55410e8fd190bf7497b46a325248e9bbf251174980ca94b0aa820e987a7d` | 14,999 | identical | identical | 0.191 | 0.59 |
| scipy | finished | 71.2 | 2,298 | `6c6a29457d283e00f14ace401960c4866d4e9a1e8395b25c3639ae11c2d29222` | `317b9c8cb3de58d89900bd64ffa2376f1daff20eb8f8036ccc16d0407402e0a8` | 15,073 | identical | identical | 0.323 | 0.60 |
| openai | finished | 27.3 | 2,050 | `6f591d617ea3f8e358c61af4c82cb12fd07b8f898327e7882fdc80dbb8ecde8f` | `7d0644ed11cfecfb058bf2b33f79b9295cd3639e1b76516992da16f0db99605d` | 14,786 | identical | identical | 0.134 | 0.44 |
| dask | finished | 23.5 | 1,714 | `59e78cad7db5b690c9c74b3d3ff137f6bced8115e519d5da999d349e7c5b33db` | `de1bbd89070753561a417c47dc554b2403b54a7e632d8d22e3f5c2285de9ccfa` | 15,056 | identical | identical | 0.190 | 0.55 |
| matplotlib | finished | 31.7 | 1,292 | `49808c5c0ea44cfb25ebe5a5706a796694a4fc26dca84831a0e15665942a5993` | `3955877e37a71e18d313473cb06f3927fc43e3360bb5085c4bb5d579379e31b5` | 15,161 | identical | identical | 0.353 | 0.68 |
| scikit-learn | finished | 151.5 | 5,056 | `86d06c93d3c004d4ffe8584dd234a73f4032629345b803451ad389ed6e4a72c5` | `da00ad0712d48f327bf10290f3f64dab0370eceeea53cfe505cf73923ef9663a` | 14,999 | identical | identical | 0.183 | 0.49 |
| sphinx | finished | 6.7 | 513 | `6ce342d2dd8a67ec7b2cc0733905a31cad9adb7520b3010afd15a5c4d9510f20` | `0b89bb0c7e158c9a98af11033a187a41e8f2715c8359c444f40d92b50f84597b` | 15,076 | identical | identical | 0.204 | 0.75 |
| sympy | crash: `internal error at crates/analysis/src/engine/arguments.rs:247:50: an index fits i64` | 142.9 | 4,256 | – | – | 14,873 | no Python document | no Python document | – | 0.34 |
| xarray | finished | 28.2 | 1,991 | `a27b3dc3914f56c4a8c89691fc00102b11c3f202d33b6af882555b011b9a9c60` | `0086314d3c787c6fbad5b07ecc81d339511e4e7cf50f012cf5f4140a0438efc6` | 15,053 | identical | identical | 0.126 | 0.60 |
| cerberus | finished | 12.6 | 422 | `909ceb867d2cbd183aca07163a6440e46b36feeee94545b746214796c589262d` | `8d828c554e2c1b997582131d6c2bdf85cf1f8983707b205fad7816e6b3c9146c` | 15,160 | identical | identical | 0.177 | 0.60 |
| python-future | finished | 35.5 | 979 | `fb3196bebc7c14b46f122230940072d71d2e49af4fbc552a86d1804a37c1aa48` | `d4ff963adc87f5c39d64ba674c4528ebad89ddfe113de49d3881701144e049a0` | 15,254 | identical | identical | 0.152 | 0.62 |
| graphene | finished | 0.8 | 171 | `1af6074fdbe736f087fda8f051f771105038f71ab5b3b3c7adedcdaca06a87d3` | `3ced3f48c17d0a92ad694802e773a1517efd606913be4b9c9b54d10a1bc3fe65` | 15,279 | identical | identical | 0.073 | 0.45 |
| elasticsearch-dsl-py | finished | 5.2 | 410 | `be9ae89413287e4db40fa151c9cc3307a0004abaed7e57add5fefed2b2449a68` | `fac8bf13804d6b3b4e050c2791e7dfa3e156d80bbe70cb5ca14929ae307ada4a` | 15,227 | identical | identical | 0.109 | 0.61 |

Intel(R) Xeon(R) Processor at 2,700 MHz, 4 cores.
