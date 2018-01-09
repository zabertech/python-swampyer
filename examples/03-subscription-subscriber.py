#!/bin/bash

from __future__ import print_function

import swampyer

import datetime
import time
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=1)

try:
    client = swampyer.WAMPClient(
                    url="ws://localhost:8282/ws",
                    uri_base="com.example.wamp.api",
                ).start()


    def time_callback(*args,**kwargs):
        print(args, kwargs)

    client.subscribe("time",time_callback)

    time.sleep(10)


except swampyer.SwampyException as ex:
    print("Whoops, something went wrong: {}".format(ex))


