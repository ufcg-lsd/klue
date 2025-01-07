#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <tag>"
    exit 1
fi

TAG=$1

sudo docker build -t sobreira155/emulation-scheduler:$TAG .
sudo docker push sobreira155/emulation-scheduler:$TAG
