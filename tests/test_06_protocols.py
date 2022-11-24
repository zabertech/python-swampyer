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

    print("Check JSON")
    client_json = connect_service(serializer_code='json')

    # Try send a string that cannot be encoded by utf8
    invalid_data = b'[' \
                    + b'\xa0\x0e\xdc\x14' \
                    + b']'
    try:
        client_json.publish(
            'com.izaber.wamp.pub.hello',
            options={
                'acknowledge': True,
                'exclude_me': False,
            },
            args=[invalid_data]
        )
    except UnicodeDecodeError as ex:
        print(f"JSON does not like non-utf8 strings {ex}")
        pass
    except Exception as ex:
        raise

    print("Check CBOR")
    client_cbor = connect_service(serializer_code='cbor')
    result = client_cbor.publish(
        'com.izaber.wamp.pub.hello',
        options={
            'acknowledge': True,
            'exclude_me': False,
        },
        args=[invalid_data]
    )

    print("Check MSGPACK")
    client_msgpack = connect_service(serializer_code='msgpack')
    result = client_msgpack.publish(
        'com.izaber.wamp.pub.hello',
        options={
            'acknowledge': True,
            'exclude_me': False,
        },
        args=[invalid_data]
    )


if __name__ == '__main__':
    test_connection()
