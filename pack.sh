#!/bin/sh
# Builds Doza-Assist.mcpb from this folder (a zip with the manifest at the root).
set -e
cd "$(dirname "$0")"
rm -f Doza-Assist.mcpb
zip -q -X Doza-Assist.mcpb manifest.json icon.png README.md run.sh server.py schema.json
echo "Doza-Assist.mcpb"
