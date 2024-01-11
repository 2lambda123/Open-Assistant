import logging
import sys
import traceback


def log_error(message):
    logging.error(message)
    print(message, file=sys.stderr)

def log_exception(exception):
    logging.exception(exception)
    traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)

def log_debug(message):
    logging.debug(message)
    print(message, file=sys.stderr)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
