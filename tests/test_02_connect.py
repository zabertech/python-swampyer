#!/usr/bin/python

import logging
import sys
import time

from lib import connect_service, load_nexus_db

logging.basicConfig(stream=sys.stdout, level=30)

def test_connection():
    snapshot_data = load_nexus_db()
    users = snapshot_data['users']
    username = 'trust-1'
    trusted_user = users[username]

    # rm:13406 - What about using False 
    try:
        cli2 = connect_service(
                    username=username,
                    password=False,
                )
        raise Exception("Should have failed")
    except Exception as ex:
        assert "No password" in str(ex), str(ex)

    # Let's see what happens if we use the wrong password
    try:
        cli2 = connect_service(
                    username=username,
                    password=trusted_user['plaintext_password'] + 'wrong'
                )
        raise Exception("Should have failed")
    except Exception as ex:
        assert "Permission Denied" in str(ex), str(ex)

    # Do a basic clean connection
    cli = connect_service()
    time.sleep(1)
    cli.shutdown()

if __name__ == '__main__':
    test_connection()


