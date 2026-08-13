#!/usr/bin/env bash
# Applies the project's own industrial weapon texture pack
# (custom-assets/weapons/) over the locally-fetched Jumpy dev assets,
# renaming 14 of Jumpy's own weapons. Run after fetch-dev-assets.sh.
#
# Only two things change per item, in place, at the item's *original*
# file path: the PNG bytes, and the `name:` line in its element.yaml.
# Everything else - atlas.yaml (tile_size/rows/columns), the mechanics
# data yaml, grab/spawn offsets, colliders, item IDs, and every
# cross-reference to this item from level files - is untouched. Every
# replacement PNG was verified byte-for-byte canvas-size-identical to the
# original it replaces before being added to custom-assets/weapons/.
#
# "Blunderbass" -> "Combat Shotgun" is intentionally NOT applied here:
# Blunderbass is an unfinished placeholder in Jumpy itself (no data/atlas/
# PNG, not placed on any shipped level), so there is no working mechanic
# to attach art to without inventing new gameplay code, which this pack
# explicitly does not do. custom-assets/weapons/combat_shotgun/ holds the
# art for whenever that gets resolved.
set -euo pipefail
cd "$(dirname "$0")/.."

PACK=custom-assets/weapons
ITEMS=assets/elements/item

apply() {
  local old="$1" new_slug="$2" new_name="$3"
  local old_texture="${4:-$old.png}"
  local src="$PACK/$new_slug/$new_slug.png"
  local dst="$ITEMS/$old/$old_texture"
  local yaml="$ITEMS/$old/$old.element.yaml"
  if [ ! -f "$src" ]; then
    echo "SKIP $old -> $new_slug: $src not found" >&2
    return
  fi
  if [ ! -f "$dst" ]; then
    echo "SKIP $old -> $new_slug: $dst not found (run fetch-dev-assets.sh first?)" >&2
    return
  fi
  cp "$src" "$dst"
  sed -i "s/^name: .*/name: $new_name/" "$yaml"
  echo "applied: $old -> $new_name"
}

apply buss          sawed_off           "Sawed-Off"
apply musket         heavy_rifle         "Heavy Rifle"
apply sniper_rifle   rail_rifle          "Rail Rifle"          sniper.png
apply machine_gun    assault_rifle       "Assault Rifle"
apply cannon         rocket_launcher     "Rocket Launcher"
apply grenade        frag_grenade        "Frag Grenade"
apply kick_bomb      explosive_canister  "Explosive Canister"
apply cannonball     plasma_core         "Plasma Core"
apply mine           proximity_mine      "Proximity Mine"
apply jellyfish      shock_drone         "Shock Drone"
apply sword          shock_baton         "Shock Baton"
apply stomp_boots    impact_boots        "Impact Boots"
apply crate          supply_case         "Supply Case"
apply periscope      tactical_scanner    "Tactical Scanner"

# stomp_boots' separate small HUD icon sheet.
icon_src="$PACK/impact_boots/impact_boots_icon.png"
icon_dst="$ITEMS/stomp_boots/stomp_boots_icon.png"
if [ -f "$icon_src" ] && [ -f "$icon_dst" ]; then
  cp "$icon_src" "$icon_dst"
  echo "applied: stomp_boots icon"
fi

echo "Done (Combat Shotgun skipped - see script header)."
