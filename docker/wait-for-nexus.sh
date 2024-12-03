#!/bin/bash

# Repeat the request every 5 seconds until a successful response is obtained
while true; do
    # Send the request and capture the HTTP status code
    status=$(curl -o /dev/null -s -w "%{http_code}\n" -H 'X-Auth-Username: admin' -H 'X-Auth-Password: admin' http://nexus-swampyer:8282/api/login)
    
    # Check if the status code indicates success (e.g., 200)
    if [ "$status" -eq 200 ]; then
        echo "Nexus server is up and responding."
        break
    else
        echo "Waiting for Nexus server to respond... (Status: $status)"
        sleep 5  # wait 5 seconds before checking again
    fi
done
