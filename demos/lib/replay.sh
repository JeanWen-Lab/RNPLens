#!/bin/bash
# replay.sh RUN_SH ORIGINAL [NEW]: run RUN_SH into NEW (default: $REPLAY_ROOT or the original's parent folder,
# <name>_replay_<utc>), then compare every *.json (created_utc / wall_s ignored). Writes ORIGINAL/checks/replay_check.json.
RUN_SH="$1"; ORIG="$(cd "$2" && pwd)"; NEW="${3:-}"
: "${RNPLENS_PY:=python}"
if [ -z "$NEW" ]; then NEW="${REPLAY_ROOT:-$(dirname "$ORIG")}/$(basename "$ORIG")_replay_$(date -u +%Y%m%dT%H%M%SZ)"; fi
bash "$RUN_SH" "$NEW" || { echo "replay run failed" >&2; exit 1; }
mkdir -p "$ORIG/checks"
"$RNPLENS_PY" "$(dirname "$RUN_SH")/../lib/compare_results.py" "$ORIG" "$NEW" "$ORIG/checks/replay_check.json"; RC=$?
# post-hoc supplement (reported separately from the pre-registered check above)
"$RNPLENS_PY" "$(dirname "$RUN_SH")/../lib/classify_replay_diffs.py" "$ORIG" "$NEW" "$ORIG/checks/replay_check.json" "$ORIG/checks/replay_diff_classification_posthoc.json"
exit $RC
