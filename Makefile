test: unit_test

unit_test:
	python3 -m unittest discover -s pycg/tests -p "*_test.py"
