#!/usr/bin/python

from common import *
import logging
import sys
import time

import swampyer


logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():
    cli = connect_service()
    time.sleep(1)
    return cli

if __name__ == '__main__':
    print(test_connection())
