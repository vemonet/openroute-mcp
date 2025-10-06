#!/bin/bash

# Script to help deploy the system on the server

OPENROUTE_MCP_FOLDER=/home/pi/dev/openroute-mcp/

# Sync files to pi
scp -r * framb:$OPENROUTE_MCP_FOLDER

ssh_cmd() {
    ssh framb "cd $OPENROUTE_MCP_FOLDER ; $1"
}
if [ "$1" = "build" ]; then
    echo "📦️ Re-building"
    ssh_cmd "docker compose up --force-recreate --build -d"
elif [ "$1" = "deploy" ]; then
    ssh_cmd "docker compose up --force-recreate -d"
elif [ "$1" = "stop" ]; then
    ssh_cmd "docker compose down"
# else
#     ssh_cmd "docker compose up --force-recreate -d"
fi
