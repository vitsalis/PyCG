import logging

class ListHandler(logging.Handler):
    def emit(self, record):
        record.getMessage()

logger = logging.getLogger("bench")
logger.addHandler(ListHandler())
logger.warning("hello")
