A method annotated to return `Self` returns the receiver. Called on a
`FancyBuilder`, the chained call goes to the subclass, so the edge
`main -> main.Builder.build` must not appear.
