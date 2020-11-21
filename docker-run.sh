#!/usr/bin/env bash 
#
# docker-run.sh
# 202011202303  
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
# Unofficial Bash Strict Mode (Unless You Looove Debugging)
set -euo pipefail

docker run -i -t -d --init --name="winix-02" \
    -v /home/user/winix:/home/user/winix \
    -v /etc/localtime:/etc/localtime:ro \
    --net=host \
    --user $(id -u):$(id -g) \
    winix-02
    