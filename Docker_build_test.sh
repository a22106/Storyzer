#!/bin/bash
docker build -t storyzer:latest .
docker run -d -p 8080:8080 storyzer:latest