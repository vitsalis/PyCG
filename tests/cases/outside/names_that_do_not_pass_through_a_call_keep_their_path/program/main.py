
import lib
import lib.sub.deep
lib.sub.helper()
lib.ITEMS[0].close()
for item in lib.ITEMS:
    item.run()
with lib.lock as held:
    held.release()
p = lib.sub
p.join()
