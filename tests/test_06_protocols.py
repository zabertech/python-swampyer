#!/usr/bin/python

from common import *
import logging
import sys

import swampyer


logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():
    print("Check CBOR")
    connect_service(serializer_code='cbor')

    # CBOR was generating errors when sending datetimes

    print("Check MSGPACK")
    connect_service(serializer_code='msgpack')

if __name__ == '__main__':
    test_connection()
