# Sourced at the end of a demo run.sh: copy the scripts into the package and write its replay.sh.
#   DEMO_DIR (the demo's script folder), OUT (package root)
mkdir -p scripts/lib "scripts/$(basename "$DEMO_DIR")"
cp "$DEMOS_LIB"/*.py "$DEMOS_LIB"/*.sh scripts/lib/
cp "$DEMO_DIR"/* "scripts/$(basename "$DEMO_DIR")/"
cat > replay.sh <<RPEOF
#!/bin/bash
# Re-run this demonstration's deterministic workflow into a NEW folder and compare every result JSON with this
# package (keys created_utc and wall_s ignored). Usage: bash replay.sh [NEW_FOLDER]
#   RNPLENS_PY: python that imports RNPLens 0.4.0.dev0 (with PYTHONPATH set as for the original run)
HERE="\$(cd "\$(dirname "\$0")" && pwd)"
exec bash "\$HERE/scripts/lib/replay.sh" "\$HERE/scripts/$(basename "$DEMO_DIR")/run.sh" "\$HERE" "\${1:-}"
RPEOF
chmod +x replay.sh
