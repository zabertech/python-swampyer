#!/usr/bin/python

from common import *
import logging
import sys

import swampyer


# We want to see the protocol information
# being exchanged
logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():
    print("Check CBOR")
    connect_service(serializer_code='cbor')
    print("Check MSGPACK")
    connect_service(serializer_code='msgpack')

if __name__ == '__main__':
    print(test_connection())
