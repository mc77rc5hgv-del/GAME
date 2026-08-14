#!/usr/bin/env bash
# Applies the project's own soldier character art (custom-assets/characters/)
# over Fishy (player 1) and Orcy (player 2) in the locally-fetched Jumpy dev
# assets. Run after fetch-dev-assets.sh.
#
# Pure filename-preserving swap, same convention as the weapon/tile packs:
# each of the 6 PNGs replaces the Jumpy original at the exact same path,
# same filename, same canvas size, same grid. The *.player.yaml files
# (stats, body_size, offsets, animation frame indices/fps) and the
# *.atlas.yaml files are never touched, so physics and animation timing
# stay exactly where they were - only the pixels change.
set -euo pipefail
cd "$(dirname "$0")/.."

PACK=custom-assets/characters
DEST=assets/player/skins

for skin in fishy orcy; do
  for layer in body face fin; do
    src="$PACK/$skin/$skin-$layer.png"
    dst="$DEST/$skin/$skin-$layer.png"
    if [ ! -f "$src" ]; then
      echo "SKIP $skin-$layer: $src not found" >&2
      continue
    fi
    if [ ! -f "$dst" ]; then
      echo "SKIP $skin-$layer: $dst not found (run fetch-dev-assets.sh first?)" >&2
      continue
    fi
    cp "$src" "$dst"
    echo "applied: $skin-$layer"
  done
done

echo "Done."
