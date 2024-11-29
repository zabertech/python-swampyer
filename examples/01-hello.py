#!/bin/bash

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
                    url="ws://NEXUS_HOST:8282/ws",
                    #url="wss://demo.crossbar.io/ws",
                    #realm="crossbardemo",
                    #auto_reconnect=3
                ).start()
    print(client)
except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


