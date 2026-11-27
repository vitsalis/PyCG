
import ext
E = ext.Error
for _ in range(3):
    try:
        pass
    except E as e:
        E = e.cause.kind
