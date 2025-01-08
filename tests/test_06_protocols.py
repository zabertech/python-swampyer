#!/usr/bin/python

import logging
import sys
from datetime import datetime

from lib import connect_service

logger = logging.getLogger(__name__)

logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

def test_connection():

    logger.info("Check JSON")
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
        # JSON does not like non-utf8 strings
        # so we expect this to happen
        pass
    except Exception:
        # If it's not a UnicodeDecodeError, then
        # something else has happened and we need
        # to raise it
        raise

    # Send a datetime object, ensure it falls back to
    # isoformat().
    obj = datetime.now()
    try:
        client_json.publish(
            'com.izaber.wamp.pub.hello',
            options={
            'acknowledge': True,
            'exclude_me': False,
            },
        args=[obj]
        )
    except Exception:
        raise

    logger.info("Check CBOR")
    client_cbor = connect_service(serializer_code='cbor')
    client_cbor.publish(
        'com.izaber.wamp.pub.hello',
        options={
            'acknowledge': True,
            'exclude_me': False,
        },
        args=[invalid_data]
    )

    logger.info("Check MSGPACK")
    client_msgpack = connect_service(serializer_code='msgpack')
    client_msgpack.publish(
        'com.izaber.wamp.pub.hello',
        options={
            'acknowledge': True,
            'exclude_me': False,
        },
        args=[invalid_data]
    )


if __name__ == '__main__':
    test_connection()
