#!/bin/bash

. /home/zaber/.poetry/env

create_work_env() {
  poetry env use $1
  poetry run python -c 'from __future__ import print_function;import sysconfig;print("mkdir -p "," ".join(sysconfig.get_paths().values()))' > /tmp/sysconfig-paths.sh
  . /tmp/sysconfig-paths.sh
  poetry install -E all
}

create_work_env "2.7"

