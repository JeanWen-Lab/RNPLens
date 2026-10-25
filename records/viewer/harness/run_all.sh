#!/bin/bash
# RNPLens viewer track driver. usage: bash run_all.sh PAGES_JSON RESULTS_DIR
# env: CHROME (chrome-headless-shell binary), PP (folder with node_modules/puppeteer-core and render.js), PY (python
# with numpy and PIL), HARNESS (folder with check_pages.py). For each page: one run with networking removed
# (bubblewrap --unshare-net: only a loopback interface exists) and one run with networking available, under
# strace -f (connect/sendto of the whole browser process tree) and with every request logged through CDP.
set -u
PAGES="$1"; OUT="$2"; mkdir -p "$OUT"
{ echo "chrome: $("$CHROME" --version 2>/dev/null)"; echo "node: $(node --version)"; echo "bwrap: $(bwrap --version)";
  echo "strace: $(strace -V | head -n 1)"; echo "puppeteer-core: $(node -e "console.log(require('$PP/node_modules/puppeteer-core/package.json').version)")";
  uname -a; } > "$OUT/environment.txt" 2>&1
"$PY" -c "import json,sys; [print(p['page_id'], p['package'] + '/' + p['viewer_dir'] + '/viewer.html') for p in json.load(open(sys.argv[1]))]" "$PAGES" |
while read -r ID HTML; do
  D="$OUT/$ID"; mkdir -p "$D"
  bwrap --unshare-net --dev-bind / / --proc /proc -- node "$PP/render.js" "$CHROME" "$HTML" "$D" offline > "$D/offline.log" 2>&1
  echo "offline exit=$?" >> "$D/offline.log"
  strace -f -qq -e trace=connect,sendto -o "$D/strace_netlog.txt" node "$PP/render.js" "$CHROME" "$HTML" "$D" netlog > "$D/netlog.log" 2>&1
  echo "netlog exit=$?" >> "$D/netlog.log"
  echo "$ID: $(head -n 1 "$D/offline.log" | cut -c1-300)"
done
"$PY" "$HARNESS/check_pages.py" "$PAGES" "$OUT" "$OUT/checks.json" > "$OUT/checks.log" 2>&1
echo "check exit=$?" >> "$OUT/checks.log"
echo DONE > "$OUT/DONE"
