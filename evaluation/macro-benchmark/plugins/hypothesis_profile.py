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
