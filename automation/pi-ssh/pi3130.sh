#!/bin/bash
# Pi SSH via the stable 198.19.0.1:3130 proxy. Usage: pi3130.sh '<remote command>'
exec ssh -i /home/hatch/.ssh/id_ed25519 \
  -o ProxyCommand="socat - PROXY:198.19.0.1:100.103.139.55:2222,proxyport=3130" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=20 -p 2222 root@100.103.139.55 "$@"
