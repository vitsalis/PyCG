test:
	SNIPPETS_PATH="pycg/test_suite/snippets" CALL_GRAPH_MODULE="pycg.pycg" CALL_GRAPH_CLASS="CallGraphGenerator" python3 -m unittest discover -s pycg/test_suite -p "*_test.py"
