test: unit_test functional_test

unit_test:
	python3 -m unittest discover -s pycg/tests -p "*_test.py"

functional_test:
	./benchmark/create_pytests.py
	SNIPPETS_PATH="benchmark/snippets" CALL_GRAPH_MODULE="pycg.pycg" CALL_GRAPH_CLASS="CallGraphGenerator" python3 -m unittest discover -s benchmark -p "*_test.py"
