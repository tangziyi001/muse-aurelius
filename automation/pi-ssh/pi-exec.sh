#!/bin/bash
# pi-exec: run a command on the Pi over the socat proxy (port 2222)
exec ssh -i /home/hatch/.ssh/id_ed25519 \
  -o ProxyCommand="/home/hatch/workspace/pi-ssh/socat_cmd.sh %h %p" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -p 2222 root@100.103.139.55 "$@"
