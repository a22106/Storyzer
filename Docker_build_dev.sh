#!/bin/bash

docker stop $(docker ps -a -q --filter ancestor=storyzer-dev:latest)

docker build -t storyzer-dev:latest -f Dockerfile-dev .
docker run -d -p 7070:7070 storyzer-dev:latest