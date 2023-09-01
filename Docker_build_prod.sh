#!/bin/bash

if [ "$(conda env list | grep '*' | awk '{print $1}')" != "api311" ]; then
    echo "You are not in the api311 conda environment. 'conda activate api311' and try again."
    exit 1
fi

docker build -t storyzer:latest .
docker run -d -p 8080:8080 storyzer:latest