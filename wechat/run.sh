#!/bin/bash
# WeChat HA Add-on entrypoint
# Starts Xvfb, then WeChat. Keeps container alive for automation.

set -e

DISPLAY_NUM="${DISPLAY_NUM:-:99}"
SCREEN="${SCREEN:-1366x768x24}"

echo "[wechat] Starting Xvfb on $DISPLAY_NUM ($SCREEN)"
Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN" &
XVFB_PID=$!
sleep 3

export DISPLAY="$DISPLAY_NUM"
export HOME="${WECHAT_HOME:-/data/wechat-home}"
mkdir -p "$HOME"

echo "[wechat] Starting WeChat (HOME=$HOME)"
# WeChat needs to run from its own directory for crashpad_handler
cd /opt/wechat
LD_LIBRARY_PATH=/opt/wechat /opt/wechat/wechat &
WECHAT_PID=$!

echo "[wechat] WeChat PID=$WECHAT_PID, Xvfb PID=$XVFB_PID"

# Screenshot helper: writes /data/shots/<name>.png
mkdir -p /data/shots

# Keep container alive; forward SIGTERM to children
trap "kill $WECHAT_PID $XVFB_PID 2>/dev/null; exit 0" SIGTERM SIGINT
wait $WECHAT_PID
