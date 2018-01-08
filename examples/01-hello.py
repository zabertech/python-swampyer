#!/bin/bash

from __future__ import print_function

import swampyer
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=1)

try:
    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws"
                ).start()
    print(client)
except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


