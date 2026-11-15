"""Third-party code that typeshed has stubs for is typed from them, exactly as
the standard library is (docs/design.md, *Outside code*): a function keeps
the path through which the code reached it, a method of a typed value is
named by the public name of its class, a stubbed function calls none of its
arguments, and the analysed package wins over any stub."""

import subprocess
import sys
import textwrap
from pathlib import Path

from programs import call_graph, callees, main_graph

ROOT = Path(__file__).resolve().parent.parent


def test_the_result_of_a_function_is_typed(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import requests
        r = requests.get("https://example.org")
        r.json()
        r.raise_for_status()
        """,
    )

    # requests.get is defined in requests.api; Response in requests.models,
    # and its public name is requests.Response.
    assert callees(graph, "main") == [
        "requests.Response.json",
        "requests.Response.raise_for_status",
        "requests.get",
    ]


def test_a_class_is_instantiated_and_its_methods_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import requests
        with requests.Session() as session:
            session.get("https://example.org").json()
        """,
    )

    # __enter__ returns Self: the session.
    assert callees(graph, "main") == [
        "requests.Response.json",
        "requests.Session",
        "requests.Session.get",
    ]


def test_an_inherited_method_is_named_by_the_class_of_the_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import requests
        session = requests.Session()
        session.get_redirect_target(session.get("u"))
        session.get("u").headers.get("Content-Type")
        class Client(requests.Session):
            pass
        Client().get("u")
        """,
    )

    # get_redirect_target is defined on SessionRedirectMixin, a base of
    # Session; headers is a CaseInsensitiveDict, whose get comes from
    # Mapping in the standard library. An analysed subclass reaches the
    # members of its outside base one step past the base.
    assert callees(graph, "main") == [
        "requests.Session",
        "requests.Session.__init__",
        "requests.Session.get",
        "requests.Session.get_redirect_target",
        "requests.structures.CaseInsensitiveDict.get",
    ]


def test_re_exports_keep_the_path_through_which_the_code_reached_them(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import yaml
        from yaml.loader import SafeLoader
        yaml.load("a: 1", Loader=yaml.SafeLoader)
        yaml.SafeLoader("a: 1").get_single_data()
        SafeLoader("a: 1").get_single_data()
        try:
            yaml.safe_load("a: 1")
        except yaml.YAMLError as error:
            error.with_traceback(None)
        """,
    )

    # yaml.load is defined in yaml. SafeLoader is defined in yaml.loader
    # and re-exported by a star import of yaml, which gives its public
    # name; get_single_data is defined on BaseConstructor, a base of
    # SafeLoader. YAMLError is defined in yaml.error, re-exported by yaml,
    # and gets with_traceback from BaseException.
    assert callees(graph, "main") == [
        "yaml.SafeLoader",
        "yaml.SafeLoader.get_single_data",
        "yaml.YAMLError.with_traceback",
        "yaml.load",
        "yaml.loader.SafeLoader",
        "yaml.safe_load",
    ]


def test_a_third_party_function_calls_none_of_its_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import requests
        import yaml
        def construct(loader, node):
            pass
        def hook(pairs):
            pass
        yaml.add_constructor("!x", construct)
        requests.get("u").json(object_hook=hook)
        list(map(hook, [1]))
        """,
    )

    # Both parameters are typed as callables; only a builtin calls back.
    assert callees(graph, "main") == [
        "<builtin>.list",
        "<builtin>.map",
        "main.hook",
        "requests.Response.json",
        "requests.get",
        "yaml.add_constructor",
    ]
    assert callees(graph, "main.construct") == []


def test_a_module_without_stubs_keeps_its_path_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import nosuchlib
        nosuchlib.Client.get().decode()
        """,
    )

    assert callees(graph, "main") == ["nosuchlib.Client.get"]


def test_a_namespace_package_of_two_distributions(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from google.protobuf import json_format
        import google.protobuf.message
        json_format.MessageToJson(google.protobuf.message.Message()).upper()
        """,
    )

    # google has no __init__.pyi: protobuf gives google.protobuf, and
    # google-cloud-ndb gives google.cloud.ndb.
    assert callees(graph, "main") == [
        "<builtin>.str.upper",
        "google.protobuf.json_format.MessageToJson",
        "google.protobuf.message.Message",
    ]


# The analysed package wins over any stub.


def test_an_analysed_package_named_like_a_stubbed_distribution(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "yaml/__init__.py": """
                class Document:
                    def run(self): pass
                def load(stream):
                    return Document()
            """,
            "main.py": """
                import yaml
                yaml.load("a: 1").run()
            """,
        },
    )

    # The stub's load returns an unknown value; the analysed one a Document.
    assert callees(graph, "main") == ["yaml.Document.run", "yaml.load"]
    assert callees(graph, "yaml.load") == []


def test_a_vendored_copy_of_a_stubbed_library(tmp_path):
    vendored = """
        class Response:
            def json(self): pass
        def get(url):
            return Response()
    """
    graph = call_graph(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/_vendor/__init__.py": "",
            "app/_vendor/requests/__init__.py": vendored,
            "app/client.py": """
                from ._vendor import requests
                def fetch():
                    return requests.get("u").json()
            """,
            "main.py": """
                from app._vendor import requests
                from app.client import fetch
                requests.get("u").json()
                fetch()
            """,
        },
    )

    expected = [
        "app._vendor.requests.Response.json",
        "app._vendor.requests.get",
    ]
    assert callees(graph, "main") == [*expected, "app.client.fetch"]
    assert callees(graph, "app.client.fetch") == expected


# Loading stays lazy.

TRACE_OPENS = """
import sys
from pathlib import Path
opened = []
def audit(event, args):
    if event == "open" and isinstance(args[0], str):
        opened.append(args[0])
sys.addaudithook(audit)
from pycg.pycg import CallGraphGenerator
root = Path(sys.argv[1])
generator = CallGraphGenerator([str(root / "main.py")], str(root))
generator.analyze()
generator.output()
for path in opened:
    if "stub_data" in path:
        print(Path(path).relative_to(Path(path).parents[1]).as_posix())
"""


def _stub_files_read(tmp_path, source):
    (tmp_path / "main.py").write_text(textwrap.dedent(source))
    result = subprocess.run(
        [sys.executable, "-c", TRACE_OPENS, str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return sorted(set(result.stdout.split()))


def test_a_program_that_imports_no_third_party_module_reads_no_third_party_data(
    tmp_path,
):
    files = _stub_files_read(
        tmp_path,
        """
        import re
        import nosuchlib
        re.compile("a").match("b").group()
        nosuchlib.run()
        """,
    )

    assert "stub_data/re.json" in files
    assert [path for path in files if "third_party" in path] == []


def test_a_program_reads_the_data_of_the_distributions_it_imports(tmp_path):
    files = _stub_files_read(
        tmp_path,
        """
        import yaml
        yaml.safe_load("a: 1")
        """,
    )

    assert [path for path in files if "third_party" in path] == [
        "third_party/yaml.json"
    ]
