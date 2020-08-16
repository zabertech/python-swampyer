#!/bin/bash

pushd "$(dirname "$0")"

if ! crossbar status --assert stopped 2> /dev/null; then

  crossbar stop

  for i in {1..40}
  do
    sleep 1s
    if crossbar status --assert stopped 2> /dev/null; then
      popd
      exit
    fi
  done

  popd
  exit 1


fi

