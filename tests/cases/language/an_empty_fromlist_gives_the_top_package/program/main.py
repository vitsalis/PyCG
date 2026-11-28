
__import__("shop.cart", fromlist=()).cart.total()
__import__("shop.cart", fromlist=[]).cart.total()
__import__("shop.cart", None, None, ()).cart.total()
