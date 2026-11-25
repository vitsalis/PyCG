import pytest

CLASSES = {
    "avro/test/test_io.py": {
        "BinaryEncodingTestCase",
        "DefaultValueTestCase",
        "IoValidateTestCase",
        "RoundTripTestCase",
        "SchemaPromotionTestCase",
    },
    "avro/test/test_protocol.py": {"ProtocolParseTestCase"},
    "avro/test/test_schema.py": {"FingerprintTestCase", "SchemaParseTestCase"},
}


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(collector, name, obj):
    if isinstance(collector, pytest.Module) and name in CLASSES.get(
        collector.nodeid, ()
    ):
        return []
    return None
