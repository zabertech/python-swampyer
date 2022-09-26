#!/bin/bash

export PATH="/home/zaber/.local/bin:$PATH"

create_work_env() {
  poetry env use $1
  poetry run python -c 'from __future__ import print_function;import sysconfig;print("mkdir -p "," ".join(sysconfig.get_paths().values()))' > /tmp/sysconfig-paths.sh
  . /tmp/sysconfig-paths.sh
  poetry install -E all
}

create_work_env "2.7"
create_work_env "3.6"
create_work_env "3.7"
create_work_env "3.8"
create_work_env "3.9"
