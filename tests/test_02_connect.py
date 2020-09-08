#!/usr/bin/python

from common import *
import logging
import sys

import swampyer


# We want to see the protocol information
# being exchanged
logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():
    connect_service()

if __name__ == '__main__':
    print(connect_service())
