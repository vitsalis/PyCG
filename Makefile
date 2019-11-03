test:
	SNIPPETS_PATH="test_suite/snippets" CALL_GRAPH_MODULE="pycg.pycg" CALL_GRAPH_CLASS="CallGraphGenerator" python3 -m unittest discover -s test_suite -p "*_test.py"
