#!/usr/bin/python

from lib import *

import swampyer

logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():
    cli = connect_service()
    time.sleep(1)
    cli.shutdown()

if __name__ == '__main__':
    test_connection()
