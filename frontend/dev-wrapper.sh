#!/usr/bin/env bash
# Wrapper so Turbopack subprocesses can find `node` on PATH when launched
# from environments that don't inherit a login-shell PATH.
#
# CRITICAL: cd into the script's directory before exec. Otherwise the cwd
# stays at the caller's location (e.g. ~/Polymarkets/), which causes
# PostCSS plugins (Tailwind v4) to start module resolution from the wrong
# directory and fail to find `tailwindcss` in node_modules.
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec /opt/homebrew/bin/node "./node_modules/next/dist/bin/next" dev "$@"
