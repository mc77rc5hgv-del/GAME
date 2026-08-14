#!/usr/bin/env bash
# Fetches Fish Folk: Jumpy's own game assets (assets/) into a LOCAL,
# gitignored directory for baseline development testing only, then
# re-applies this project's local overlays on top (RU locale, critter
# removal, industrial weapon textures).
#
# These assets are Copyright (c) 2020-2024 The Fish Folk Game & Spicy
# Lobster Developers, licensed CC BY-NC 4.0 (non-commercial). They must
# NEVER be committed to this repository or shipped in any build that is
# publicly deployed or monetized (including Yandex Games). See
# THIRD_PARTY_NOTICES.md. Before any real release, assets/ must be fully
# replaced with the project's own art (e.g. legacy-assets/) or other
# properly licensed content.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d assets ]; then
  echo "assets/ already exists locally - skipping the base fetch, re-applying local overlays only."
else
  REF="${1:-main}"
  echo "Fetching Jumpy's dev-only assets (ref: $REF) into ./assets (gitignored, non-commercial use only)..."
  git clone --depth 1 --branch "$REF" https://github.com/fishfolk/jumpy.git .jumpy-upstream-tmp
  mv .jumpy-upstream-tmp/assets ./assets
  rm -rf .jumpy-upstream-tmp
fi

# Overlay this project's own (original, committed) Russian localization as
# an additional locale, so the Yandex language bridge has something real to
# switch to locally. Additive only - Jumpy's own en-US/fr-FR are untouched.
# Idempotent: safe to re-run even if already applied.
if [ ! -d assets/locales/ru-RU ]; then
  cp -r localization/ru assets/locales/ru-RU
  sed -i '/^locales:/a\  - ru-RU/locale.yaml' assets/locales/localization.yaml
fi

# Project preference: no ambient sea creatures / animated coral-like
# decoration on the levels. Pure awk (no python3 dependency - Windows Git
# Bash users often only have a non-functional python3 App Execution Alias
# stub, which used to silently break this step and everything after it).
# Idempotent: matches nothing to remove on a file that's already patched.
for f in assets/map/levels/*.map.yaml; do
  awk -f scripts/strip-decorative-critters.awk "$f" > "$f.tmp"
  mv "$f.tmp" "$f"
done

# This project's own industrial weapon texture pack over 14 of Jumpy's
# weapons. Also idempotent (re-copies the same files, re-sets the same name).
bash scripts/apply-weapon-textures.sh

# This project's own static background image, replacing the 4-layer
# parallax on all 14 levels. Idempotent (rewrites the background: block
# unconditionally, whatever its current content).
bash scripts/apply-background.sh

# This project's own soldier character art over Fishy (P1) and Orcy (P2).
# Also idempotent (re-copies the same files).
bash scripts/apply-character-textures.sh

echo "Done. Remember: assets/ is for local baseline testing only, never for a shipped build."
