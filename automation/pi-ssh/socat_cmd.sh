#!/bin/bash
# SOCAT-based ProxyCommand for Pi SSH (faster/more robust than proxy_cmd.py)
PU=$(python3 -c "import os,urllib.parse; u=urllib.parse.urlparse(os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')); print(f'{u.hostname}:{3130}:{urllib.parse.unquote(u.username or \"\")}:{urllib.parse.unquote(u.password or \"\")}')")
PH=$(echo "$PU" | cut -d: -f1); PPORT=$(echo "$PU" | cut -d: -f2); PAUTH=$(echo "$PU" | cut -d: -f3-)
exec socat - "PROXY:$PH:$1:$2,proxyport=$PPORT,proxyauth=$PAUTH"
