#!/bin/sh
# Doza Assist Desktop Extension launcher. Runs the local MCP server with the
# Python bundled inside the installed Doza Assist app (no system Python needed).
# The server finds the backend through the app's backend.json.
HERE="$(cd "$(dirname "$0")" && pwd)"
REL="Contents/Resources/python/bin/python3"
try() { [ -n "$1" ] && [ -x "$1/$REL" ] && exec "$1/$REL" "$HERE/server.py"; }
try "$DOZA_APP"
try "/Applications/Doza Assist.app"
try "$HOME/Applications/Doza Assist.app"
try "/Applications/Doza Assist (Studio).app"
# Last resort: any copy Spotlight knows about (dist/ test builds included).
for app in $(mdfind "kMDItemCFBundleIdentifier == 'com.dozavisuals.dozaassist.electron' || kMDItemCFBundleIdentifier == 'com.dozavisuals.dozaassist.studio'" 2>/dev/null | tr ' ' '\001'); do
  try "$(printf '%s' "$app" | tr '\001' ' ')"
done
echo "[doza-mcp] Doza Assist.app not found. Install it in /Applications, or set the app folder in the extension's settings." >&2
exit 1
