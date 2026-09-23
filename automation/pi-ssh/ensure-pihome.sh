#!/bin/bash
# /root is ephemeral: recreate /root/.ssh/config (pihome alias) if missing.
# Run this before any `ssh pihome` in a fresh session.
if ! ssh -G pihome 2>/dev/null | grep -q "^hostname 100.103.139.55"; then
  mkdir -p /root/.ssh && chmod 700 /root/.ssh
  cp ~/workspace/pi-ssh/pihome-ssh-config /root/.ssh/config && chmod 600 /root/.ssh/config
  echo "pihome config restored to /root/.ssh/config"
fi
