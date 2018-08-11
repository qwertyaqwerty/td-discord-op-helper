#!/bin/bash

while true; do
    ps aux | grep 'main.py' | grep -v 'grep'
    if [ "$?" -eq 1 ]; then
        python3 main.py &
    fi
    sleep 10
done

