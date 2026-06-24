#!/bin/zsh
set -e

cd "$(dirname "$0")"
clear

echo "MTU Pack Editor"
echo "Starting local server..."
echo

python3 scripts/dev_server.py --open-browser
