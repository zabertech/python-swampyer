#!/bin/bash

# Go into the project's source dir
cd /src

# Then run the nox test scripts
nox --reuse-existing-virtualenvs $@

