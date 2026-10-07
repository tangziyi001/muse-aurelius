#!/bin/bash
# helper: run a command on the Pi via the legacy socat path
exec ssh -i /home/hatch/.ssh/id_ed25519 \
  -o ProxyCommand="/home/hatch/workspace/pi-ssh/socat_cmd.sh %h %p" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=30 -p 2222 root@100.103.139.55 "$@"
