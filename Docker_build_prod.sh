#!/bin/bash

docker stop $(docker ps -a -q --filter ancestor=storyzer:latest)

docker build -t storyzer:latest .
docker run -d -p 8080:8080 storyzer:latest