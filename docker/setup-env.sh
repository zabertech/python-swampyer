#!/bin/bash

ROOT_PATH=$(dirname $(readlink -f $0))

# This will ensure that poetry will execute
export PATH="/home/zaber/.local/bin:$PATH"
cd /src

# We sometimes need to upgrade
poetry update

# Now do the install process for the library
poetry install


