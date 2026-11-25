A function is defined but never called. It is a node without incoming edges, and the call in its body is not an edge.
Precision: there are no edges `main -> main.unused` and `main.unused -> main.func2`.
