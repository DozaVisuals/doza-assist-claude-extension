#!/bin/sh
# Doza Assist plugin launcher. Runs server.py (next to this file) with the
# Python bundled inside the installed Doza Assist app, so no system Python is
# needed and nothing is downloaded. server.py finds the running app through
# the backend.json the app writes in ~/Library/Application Support/DozaAssist/.
# Keep this folder named mcp/: Doza Assist's start-up clean-up of leftover
# processes on its bundled Python leaves anything running .../mcp/server.py
# alone, so opening or restarting the app never stops this connector.
HERE="$(cd "$(dirname "$0")" && pwd)"
REL="Contents/Resources/python/bin/python3"
# -B: never write __pycache__ into the app bundle (it breaks its code seal).
try() { [ -n "$1" ] && [ -x "$1/$REL" ] && exec "$1/$REL" -B "$HERE/server.py"; }
try "/Applications/Doza Assist.app"
try "$HOME/Applications/Doza Assist.app"
try "/Applications/Doza Assist (Studio).app"
try "$HOME/Applications/Doza Assist (Studio).app"
# Last resort: any copy Spotlight knows about, wherever it is installed.
for app in $(mdfind "kMDItemCFBundleIdentifier == 'com.dozavisuals.dozaassist.electron' || kMDItemCFBundleIdentifier == 'com.dozavisuals.dozaassist.studio'" 2>/dev/null | tr ' ' '\001'); do
  try "$(printf '%s' "$app" | tr '\001' ' ')"
done
echo "[doza-mcp] Doza Assist.app not found. Install Doza Assist in Applications (https://doza.ai/download) and open it." >&2
exit 1
