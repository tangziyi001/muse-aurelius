#!/bin/bash
# launch_cao.sh — (re)launch etsy_create_app_only.py on the Pi.
#
# WHY THIS WRAPPER EXISTS:
#   pkill -f "etsy_create_app_only.py" run directly inside an ssh remote
#   command matches the remote shell's OWN command line (the pattern text is
#   part of it) and kills the shell that is doing the launching. Result: the
#   script never starts and every pgrep "RUNNING" check is a false positive
#   for the same reason.
# RULE: the ssh command line that invokes this wrapper must NOT contain the
#   literal script filename. Inside the wrapper, the [.] regex trick is safe
#   because this shell's cmdline is just "bash .../launch_cao.sh".
pkill -f "etsy_create_app_only[.]py"
sleep 1
cd /config/etsy-browser || exit 1
rm -f shots/cao_run1.log shots/etsy_app_result.json
nohup python3 -u etsy_create_app_only.py > shots/cao_run1.log 2>&1 &
echo "LAUNCHED pid $!"
