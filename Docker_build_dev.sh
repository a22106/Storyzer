#!/bin/bash

if [ "$(conda env list | grep '*' | awk '{print $1}')" != "api311" ]; then
    echo "You are not in the api311 conda environment. 'conda activate api311' and try again."
    exit 1
fi

docker build -t storyzer-dev:latest -f Dockerfile-dev .
docker run -d -p 7070:7070 storyzer-dev:latest