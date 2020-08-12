#!/bin/bash

if ! crossbar status --assert stopped; then

  crossbar stop

  for i in {1..40}
  do
    sleep 1s
    if crossbar status --assert stopped; then
      exit
    fi
  done

  exit 1


fi

