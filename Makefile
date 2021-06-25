test:
	python3 -m unittest discover -s pycg/tests -p "*_test.py"

functional_test:
	./micro-benchmark/create_pytests.py
	SNIPPETS_PATH="micro-benchmark/snippets" CALL_GRAPH_MODULE="pycg.pycg" CALL_GRAPH_CLASS="CallGraphGenerator" python3 -m unittest discover -s micro-benchmark -p "*_test.py"

key_err_test:
	./micro-benchmark-key-errs/create_pytests.py
	SNIPPETS_PATH="micro-benchmark-key-errs/snippets" CALL_GRAPH_MODULE="pycg.pycg" CALL_GRAPH_CLASS="CallGraphGenerator" python3 -m unittest discover -s micro-benchmark-key-errs -p "*_test.py"
