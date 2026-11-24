"""A pytest plugin of the traces of projects whose tests use Hypothesis
(projects.toml `plugins`): it registers and loads the profile `trace`.

- deadline=None: Hypothesis fails an example that takes longer than its
  deadline (200 ms by default); under the tracer every call is slower, so a
  test that passes without the tracer would fail with it.
- database=None: the example database is a directory, .hypothesis/examples
  in the working directory, which is the source copy; the run fails if it
  changes the source copy.
- derandomize=True: the examples come from a fixed seed, so that two traces
  of the same project draw the same examples and can have the same edges.
- suppress_health_check, every health check: a health check fails a test
  whose examples are slow to generate (too_slow) or large, filtered or
  otherwise suspect; under the tracer generation is slower, so a suite that
  passes without the tracer must not fail its health checks with it.
- the storage directory: Hypothesis also caches data outside the database
  (the Unicode character map of text strategies) in .hypothesis/ of the
  working directory; it goes to a new directory below TMPDIR, which
  trace.py makes for the run and deletes after it.

Hypothesis's own pytest plugin is not loaded (trace.py disables plugin
autoloading); @given tests run without it. This module is client code for
the tracer.
"""

import tempfile

from hypothesis import HealthCheck, configuration, settings

configuration.set_hypothesis_home_dir(tempfile.mkdtemp(prefix="hypothesis-"))
settings.register_profile(
    "trace",
    deadline=None,
    database=None,
    derandomize=True,
    suppress_health_check=list(HealthCheck),
)
settings.load_profile("trace")
