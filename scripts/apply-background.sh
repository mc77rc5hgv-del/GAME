#!/usr/bin/env bash
# Replaces all 14 levels' 4-layer parallax background with a single static
# image (custom-assets/background/background_ruins.png), applied uniformly
# since every level shares the exact same background{speed,layers} block
# (only background_color, a separate ambient tint key, varies per level and
# is left untouched). Run after fetch-dev-assets.sh.
#
# Only the `background:` block is rewritten - tile layers (platforms,
# collision), elements (weapons/spawners) and background_color are
# byte-for-byte unchanged, so nothing about level geometry or gameplay
# moves. Idempotent (matches nothing to replace on an already-patched file).
set -euo pipefail
cd "$(dirname "$0")/.."

PACK=custom-assets/background/background_ruins.png
DEST=assets/map/resources/background_ruins.png

if [ ! -f "$PACK" ]; then
  echo "SKIP: $PACK not found" >&2
  exit 0
fi
cp "$PACK" "$DEST"

for f in assets/map/levels/*.map.yaml; do
  awk '
    /^background:/ { skip = 1 }
    /^background_color:/ { skip = 0 }
    skip { next }
    { print }
  ' "$f" > "$f.tmp"

  awk '
    /^background_color:/ && !done {
      print "background:"
      print "  speed:"
      print "  - 0.0"
      print "  - 0.0"
      print "  layers:"
      print "  - image: /map/resources/background_ruins.png"
      print "    size:"
      print "    - 1667.0"
      print "    - 943.0"
      print "    depth: 6.0"
      print "    scale: 2.0"
      print "    offset:"
      print "    - 0.0"
      print "    - 0.0"
      done = 1
    }
    { print }
  ' "$f.tmp" > "$f"
  rm -f "$f.tmp"
done

echo "applied: background_ruins.png (static, single layer) on all levels"
