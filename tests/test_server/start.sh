#!/bin/bash

if ! crossbar status --assert running; then

  crossbar start &

  for i in {1..40}
  do
    sleep 1s
    if crossbar status --assert running; then
      exit
    fi
  done

  exit 1

fi

