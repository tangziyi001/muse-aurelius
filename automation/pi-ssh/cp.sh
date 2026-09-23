#!/bin/bash
# Pi scp 快捷： cp.sh <local...> | cp.sh -r <...>  (目标含 root@100.103.139.55: 时为上传)
exec scp -i /home/hatch/.ssh/id_ed25519 -P 2222 \
  -o ProxyCommand="/home/hatch/workspace/pi-ssh/socat_cmd.sh %h %p" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"
