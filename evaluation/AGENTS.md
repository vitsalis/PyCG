# Agent instructions: evaluation

`README.md` says what is here and how to run it.

- **Third-party code is fetched and run only inside Docker.** The sources
  of the macro-benchmark come from the build of the inputs image
  (`container/Dockerfile.inputs`), and a project's tests run only in its
  trace container. Never `git clone`, `git fetch` or `pip install` a
  benchmark project on the host. PyCG reads the copied sources
  statically; `make eval` runs it in a container all the same.
- **Ground truths are independent of the tool.** A ground truth states
  what Python does when the code runs. Never edit a ledger, a
  `ground-truth/*.json`, a trace or `common/same_function.json` to match
  PyCG's output.
- **Stage files by name.** `macro-benchmark/projects/` and
  `results/trace/` hold fetched or generated files; never `git add -A`.
