#!/usr/bin/python

import logging
import sys
import re
from lib import connect_service

import swampyer
from swampyer.messages import AUTHENTICATE

logging.basicConfig(stream=sys.stdout, level=30)
# We want to see the protocol information
# being exchanged
#logging.basicConfig(stream=sys.stdout, level=1)

"""
@chead discovered that when debugging was turned on, the full AUTHORIZE message was sent
to the user. We make sure we don't leak the password when running debugging. Instead of
capturing the debug output, we're hooking into the lower level message that creates
the debug log message and verifying that.
"""

def test_debug_output():
    # Creates an AUTHENTICATE message that holds data related to a login
    auth_message = AUTHENTICATE(
                        signature = "HIDE_ME",
                        extra = {}
                    )
    dump = auth_message.dump()

    # We should not have the "HIDE_ME" string anywhere in the output
    matched = re.search('HIDE_ME', dump)
    assert not matched

    # We should see the signature as '******' instead
    assert re.search(r'signature: \*{6}', dump)


if __name__ == '__main__':
    test_debug_output()

