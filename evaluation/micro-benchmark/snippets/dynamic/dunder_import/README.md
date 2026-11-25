`__import__("shop.cart")` imports the submodule but returns the top-level package `shop`, so the call goes through `package.cart.total()`.
