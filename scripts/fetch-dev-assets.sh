#!/usr/bin/env bash
# Fetches Fish Folk: Jumpy's own game assets (assets/) into a LOCAL,
# gitignored directory for baseline development testing only.
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
  echo "assets/ already exists locally, nothing to do."
  exit 0
fi

REF="${1:-main}"
echo "Fetching Jumpy's dev-only assets (ref: $REF) into ./assets (gitignored, non-commercial use only)..."
git clone --depth 1 --branch "$REF" https://github.com/fishfolk/jumpy.git .jumpy-upstream-tmp
mv .jumpy-upstream-tmp/assets ./assets
rm -rf .jumpy-upstream-tmp

# Overlay this project's own (original, committed) Russian localization as
# an additional locale, so the Yandex language bridge has something real to
# switch to locally. Additive only - Jumpy's own en-US/fr-FR are untouched.
cp -r localization/ru assets/locales/ru-RU
sed -i '/^locales:/a\  - ru-RU/locale.yaml' assets/locales/localization.yaml

# Project preference: no ambient sea creatures / animated coral-like
# decoration on the levels. See scripts/strip-decorative-critters.py.
python3 scripts/strip-decorative-critters.py

echo "Done. Remember: assets/ is for local baseline testing only, never for a shipped build."
