#!/bin/bash

"""
This is an example where a unix socket is used rather than a direct
TCP socket. In this case the crossbar server must be running on the
local machine.

See more information about configuring Crossbar for local rawsockets
here:

- https://crossbar.io/docs/RawSocket-Transport/?highlight=transport#connecting-transports
- https://crossbar.io/docs/Transport-Endpoints/#unix-domain-connecting-endpoints

See the tests/test_server/.crossbar/config.yaml file for an example
configuration for the crossbar server.
"""

from __future__ import print_function

import websocket
import swampyer
import sys
import logging

# Produce lots of data
# websocket.enableTrace(True)

# We want to see the protocol information
# being exchanged
logging.basicConfig(stream=sys.stdout, level=1)

try:
    client = swampyer.WAMPClient(
                    url="unix:///tmp/nexus.socket",
                ).start()
    print(client)
except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


