# Memory census of pip, pandas and sympy

Build: `vitsalis/scratch-census` at fe609890 (main's pycg plus the census of
`crates/analysis/src/engine/census.rs`). Machine: the 16 GB cloud sandbox, 4
cores, no swap, about 15.2 GB free at the start of each run. Every run ran on
its own. The memory cap was 13312 MiB in a 13824 MiB container.

Files in this directory:

| File | Run |
|---|---|
| `pip.stderr`, `pip.record.json` | `make eval-scale NAME=pip SCALE_MEMORY_MIB=13312` |
| `pandas.stderr`, `pandas.record.json` | `make eval-scale NAME=pandas SCALE_MEMORY_MIB=13312` |
| `sympy.stderr`, `sympy.record.json` | `make eval-scale NAME=sympy SCALE_MEMORY_MIB=13312` (timeout 1800 s) |
| `sympy-long.stderr`, `sympy-long.record.json` | the `measure.py run ... --timeout 7200` command of the task |

How the runs were made:

1. `make eval-inputs` pulled the inputs images (key `67b95144…`) from
   ghcr.io.
2. `cargo fetch --locked` ran in the pinned Rust image with the proxy's CA,
   and `make` then built offline from that cache.
3. The host's `python3` is 3.13, and `measure.py container-mib` does not
   parse under 3.13 (`except A, B:`). So `make` got an empty container size
   and `docker run` failed. Each `make eval-scale` therefore had
   `SCALE_CONTAINER_MIB=13824` added: that is the value that
   `measure.py container-mib 13312` prints in the runner image, and the same
   value as the long sympy command.

The estimated bytes below are the census's `est_bytes` fields. They count
only the inline size of a few tables, so the sum is well below RSS: 3.7 of
6.1 GiB for pandas at the end of the solve, and 5.3 of 12.3 GiB for sympy at
12 GiB.

## Outcomes

| Package | Files | Outcome | Seconds | Wall seconds | Peak MiB |
|---|---|---|---|---|---|
| pip | 406 | finished | 29.4 | 29.6 | 794 |
| pandas | 1440 | finished | 249.7 | 250.5 | 8042 |
| sympy (1800 s timeout) | 1530 | killed by the cap | - | 369.1 | 13354 |
| sympy (7200 s timeout) | 1530 | killed by the cap | - | 367.0 | 13330 |

sympy does not reach the timeout in this sandbox. It reaches 13 GiB after
about 6 minutes, so the longer timeout changes nothing. In the two sympy
runs, every table of the 4 GiB and 8 GiB dumps is identical. The 12 GiB dumps
differ slightly because RSS is checked only every 65536 steps. The analysis
below uses the first run. Both runs print their last dump at 12 GiB
(elapsed 333 s) and are killed about 35 s later, before the next periodic
dump.

pandas: its RSS is 6132 MiB at the `end` dump (end of the solve, 233 s), but
its peak is 8042 MiB. So about 1.9 GiB is used after the solve, while the
graph is built and the 112 MB document is written. The census does not see
that phase. On the 8 GiB VM, this post-solve phase alone puts pandas over
the limit.

## Where the memory goes

Largest estimated structures at the last dump of each run:

| Structure | pip (end, 728 MiB RSS) | pandas (end, 6132 MiB RSS) | sympy (12 GiB dump, 12289 MiB RSS) |
|---|---|---|---|
| SOLVER successors (subset edges) | 30 MiB | 57 MiB | **2737 MiB** |
| SOLVER nodes | 96 MiB | **1536 MiB** | 1536 MiB |
| CALLS calls | 17 MiB | **1088 MiB** | 272 MiB |
| RULES | 48 MiB | **768 MiB** | 384 MiB |
| SETS elements | 21 MiB | 214 MiB | 150 MiB |
| SOLVER constraints | 19 MiB | 17 MiB | 138 MiB |
| CHAINS links + extensions | 10 MiB | 5 MiB | 19 MiB |

The SOLVER nodes, CALLS and RULES figures are capacities of vectors that
grow by doubling. pandas has 8.9 M nodes in a 16.8 M slot vector, 5.3 M
calls in 8.4 M slots and 25.6 M rules in 33.6 M slots.

The successors estimate for sympy is a lower bound. The census counts 10
bytes per edge at the edges' length. A `Targets` stores each edge twice: once
in a `Vec<NodeId>` (4 bytes) and once in an `FxHashMap<NodeId, bool>` (8
bytes plus a control byte, at a load of at most 7/8). Both grow by doubling.
That puts the real cost at about 14 to 29 bytes per edge, or 3.7 to 7.5 GiB
for sympy's 282 M edges. This inference comes from the type layout, not from
a measurement. Most of the 7 GiB that the estimates leave unexplained at 12
GiB fits in that range. The next largest uncounted tables are WAITING
(18.3 M holders), `cycle_suspects` (6.5 M), `labels` (4.1 M named nodes) and
`reader_receivers` (5.8 M).

## sympy: growth from the 4 GiB dump to the kill

| Metric | 4 GiB (150 s) | 8 GiB (253 s) | periodic (314 s, 10935 MiB) | 12 GiB (333 s) | 12 GiB / 4 GiB |
|---|---|---|---|---|---|
| NODES succ_many_len (subset edges) | 16.5 M | 128.8 M | 201.5 M | 281.9 M | **17.1x** |
| est. successors bytes | 173 MiB | 1266 MiB | 1961 MiB | 2737 MiB | **15.8x** |
| COUNTS add_edge | 31.9 M | 172.2 M | 254.9 M | 338.4 M | **10.6x** |
| CROSS constraints × objects | 115 M | 932 M | 971 M | 998 M | 8.7x |
| NODES held_objects | 155 M | 860 M | 860 M | 860 M | 5.6x |
| WAITING held_elements | 5.9 M | 24.3 M | 32.0 M | 33.6 M | 5.7x |
| WAITING holders | 5.2 M | 13.3 M | 17.2 M | 18.3 M | 3.6x |
| NODES constraints | 9.0 M | 19.7 M | 25.5 M | 27.1 M | 3.0x |
| SETS elements | 10.8 M | 28.5 M | 29.2 M | 29.2 M | 2.7x |
| TYPEMETHOD rules (= groups) | 23 444 | 45 241 | 50 127 | 52 134 | 2.2x |
| COUNTS add_object | 38.7 M | 72.8 M | 84.5 M | 86.8 M | 2.2x |
| RULES live | 8.5 M | 12.9 M | 15.5 M | 15.9 M | 1.9x |
| BINDS instance_receivers | 2.17 M | 3.59 M | 3.85 M | 3.85 M | 1.8x |
| LOOKUPS with_instance_receiver | 423 k | 689 k | 736 k | 736 k | 1.7x |
| NODES n | 5.6 M | 8.0 M | 8.2 M | 8.5 M | 1.5x |
| CALLS calls | 878 k | 1027 k | 1054 k | 1060 k | 1.2x |
| OBJECTS total | 485 k | 546 k | 566 k | 568 k | 1.2x |
| NODES saturated | 82 | 128 528 | 128 528 | 128 528 | |

The subset edges grow fastest, and they are the only large structure that
still grows quickly after 8 GiB. From 8 GiB to 12 GiB, the edges grow from
129 M to 282 M, while the points-to sets have stopped: held_objects stays at
859.6 M and SETS elements at 29.2 M. Objects, calls, binds and lookups stay
almost flat. RSS rises 4 GiB in those 80 s, and only the edges, WAITING and
the solver's constraints grow with it.

## sympy: cross products bounded by the cap

The numbers point to cross products of sets that sit just below the cap (5000
objects per node, `CAP_DEFAULT_OBJECTS`), not to per-receiver bookkeeping:

- The CROSS product reaches 998 M: 199 834 nodes hold 1001–4999 objects and
  carry 225 175 constraints. The largest node holds 4326 objects.
- The 5000+ bucket is empty because a node over the cap becomes saturated.
  128 528 nodes are saturated by the 8 GiB dump, and the CROSS figure counts
  them as 0 objects.
- The largest objects per application are all near the cap:
  - `Protocol(Operand)`: 4698;
  - `ReturnedByItsNew`: 4709;
  - `Container(Subscript)`: 4705;
  - `Access`: 4750;
  - `ClassTest(Value)`: 4901.
- Total applications (`applied_total`): 631 M. The largest by objects:

  | Rule | Calls | Objects | Max objects | ms |
  |---|---|---|---|---|
  | `Container(KeyLookupStored)` | 84 823 | 65.8 M | 1867 | 1254 |
  | `Protocol(Operand)` | 481 470 | 54.9 M | 4698 | 98 965 |
  | `ReturnedByItsNew` | 54 473 | 49.9 M | 4709 | 17 270 |
  | `Container(SpecialCall)` | 381 087 | 40.5 M | 1867 | 8 551 |
  | `ReturnedByNew` | 34 754 | 40.0 M | 4295 | 891 |

- Most objects are containers, not instances: 231 326 `Container` objects
  against 10 174 `Instance` objects. The large sets are sets of containers.
- `add_edge` (338 M) is close to the number of subset edges (282 M). Most
  edges are added per object when a constraint applies to a large set.

Per-receiver bookkeeping exists but stays moderate, and it stops growing
after 8 GiB:

- BINDS holds 3.85 M instance receivers.
- LOOKUPS holds 736 k lookups with an instance receiver, at most 6408 per
  class.
- TypeMethod has 52 134 live rules in 52 134 groups by (call, class): one
  rule per group, not spread over many groups. Its rules were applied
  19.7 M times, one object each.
- `Container(SequenceType)` was applied 2.56 M times, one object each, and
  has too few live rules to appear in the top 25. `Container(Sequences)` has
  2.41 M live rules, the third largest kind.
- The live rules are led by `Bind` (3.94 M), `Deliver` (2.91 M),
  `Container(Sequences)` (2.41 M), `Call` (1.06 M) and `ClassTest(Related)`
  (0.96 M), 15.9 M in all. The estimated cost of the rules is 384 MiB.

## pandas against pip

pandas is the opposite case: per-receiver bookkeeping with small sets.

| Metric | pip (end) | pandas (4 GiB) | pandas (end) | pandas / pip at the end |
|---|---|---|---|---|
| OBJECTS Instance | 4 166 | 200 326 | 1 415 210 | 340x |
| OBJECTS BoundMethod | 49 845 | 203 974 | 1 241 112 | 25x |
| BINDS receiver_entries (instance) | 161 k (158 k) | 704 k (302 k) | 2.19 M (1.74 M) | 14x (11x) |
| BINDS shared_items | 13 467 | 11.1 M | 15.9 M | 1177x |
| LOOKUPS with_instance_receiver | 124 k | 202 k | 1.25 M | 10x |
| CALLS calls (dunder_calls) | 124 k (15 k) | 4.11 M (3.70 M) | 5.31 M (4.82 M) | 43x (315x) |
| RULES live | 1.54 M | 17.3 M | 25.6 M | 17x |
| TYPEMETHOD rules (= groups) | 2 826 | 3 371 | 6 712 | 2.4x |
| NODES n | 0.90 M | 6.1 M | 8.9 M | 10x |
| NODES constraints | 3.49 M | 1.60 M | 3.58 M | 1.0x |
| NODES succ_many_len | 2.17 M | 10.5 M | 5.15 M | 2.4x |
| NODES held_objects | 96.9 M | 14.4 M | 6.9 M | 0.07x |
| CROSS constraints × objects | 58.1 M | 14.5 M | 3.0 M | 0.05x |
| nodes with 1001–4999 objects | 41 914 | 0 | 0 | |
| largest max_objects of an application | 3947 (`Protocol(Operand)`) | 324 (`ClassTest(Value)`) | 324 (`ClassTest(Value)`) | |
| applied_total | 65.4 M | 12.8 M | 23.8 M | 0.4x |

- pandas makes 1.42 M instances, and 1.24 M bound methods on them.
  - Each instance gets binds (1.74 M instance receivers) and lookups (1.25 M
    with an instance receiver; at most 69 964 for one class).
  - It also gets dunder calls: 4.82 M of the 5.31 M calls.
  - These come with rules: `New`, `PythonNew` and `ReturnedOfClass` have
    4.75 M live rules each, `Call` 5.31 M, `Bind` 2.19 M and
    `PythonInstance` 1.61 M.
  - Those are the tables that dominate its estimated bytes: nodes
    1536 MiB, calls 1088 MiB, rules 768 MiB.
  - BINDS `shared_items` reaches 15.9 M, and the `Shared` rule takes 15.9 s.
- pandas' sets stay small. No node holds more than 1000 objects at the end,
  no application touches more than 324 objects, and the CROSS product is
  3.0 M, a twentieth of pip's.
- pip has the sympy shape at a small scale: 41 914 nodes of 1001–4999
  objects, applications of up to 3947 objects and a CROSS of 58 M. But
  it has only 2.2 M subset edges, and it finishes in 29 s at 794 MiB.
- TypeMethod is one rule per group in all three packages. It does not spread
  in any of them.

The census leaves one fact unexplained. At the end of pandas' solve,
3 637 804 nodes are counted as saturated (3 289 568 at 212 s, 1 at the 4 GiB
dump), although no set comes near the cap. The census reports
`done == saturated_set`, and these nodes reached that state by some other
path than the cap.

## In short

| Package | Kind of growth | Numbers that show it |
|---|---|---|
| sympy | Cross products bounded by the cap | The subset edges grow 17x from 4 to 12 GiB (16.5 M to 282 M), on 200 k nodes of 1001–4999 objects. Instances and bookkeeping stay flat after 8 GiB. |
| pandas | Per-receiver bookkeeping | 1.42 M instances, 4.8 M dunder calls, 25.6 M rules, 1.25 M instance lookups. Sets stay under 325 objects. About 1.9 GiB is added after the solve. |
| pip | sympy's shape, small | 42 k nodes of 1001–4999 objects, CROSS 58 M, 2.2 M edges, 794 MiB. |
