#!/bin/bash
# launch_pi.sh — generic Pi script launcher (self-kill-safe).
#
# Usage (from the VM, TWO ssh calls or one combined):
#   1. printf '<script.py>\n<logfile.log>\n' > /config/etsy-browser/shots/launch_target.txt
#      (this ssh command line contains no pkill, so the literal filename is safe here)
#   2. bash /config/etsy-browser/launch_pi.sh
#
# The target filename NEVER appears in the ssh command line of step 2, so
# pkill -f cannot match the invoking shell. Inside, the [.] regex trick adds
# a second layer of safety.
TGT=$(sed -n '1p' /config/etsy-browser/shots/launch_target.txt | tr -d '\r')
LOG=$(sed -n '2p' /config/etsy-browser/shots/launch_target.txt | tr -d '\r')
[ -z "$TGT" ] && { echo "no target"; exit 1; }
PAT="${TGT%.py}[.]py"
pkill -f "$PAT"
sleep 1
cd /config/etsy-browser || exit 1
rm -f "shots/${LOG}" shots/otp_code.txt shots/etsy_app_result.json shots/login_and_create_app_result.json
nohup python3 -u "$TGT" > "shots/${LOG}" 2>&1 &
echo "LAUNCHED $TGT pid $!"
