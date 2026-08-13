# Asset extraction pipeline

The texture pack's source sheets (in the original delivered pack, not
committed to this repo) are flattened presentation collages — a dark
gradient background, drop shadows, text captions, uneven spacing between
items — not pre-sliced, alpha-clean game frames. Everything in
`public/assets/` was cropped out of those sheets offline. This doc exists so
that process is reproducible if the pack is regenerated or extended, without
having to rediscover it from scratch.

## Tools

Python 3 + `Pillow` + `numpy` + `scipy.ndimage`. No project dependency on
these — it's a one-off offline step, not part of the build.

## Method

### 1. Clean sheets (weapons, projectiles, effects, HUD, arena blocks)

Most sheets place each sprite with generous transparent padding around it,
so a straightforward connected-component pass works:

1. Threshold the alpha channel (`alpha > 10`) into a binary mask.
2. Label 8-connected components (`scipy.ndimage.label`).
3. Drop components that are either too small (anti-aliasing noise) or too
   short (`height < ~35px`, catches text captions) or near-perfectly
   rectangular with high fill ratio (catches the solid-color label boxes,
   e.g. "ОРУЖИЕ (5 ВИДОВ)").
4. What's left, sorted left-to-right, is one bounding box per sprite. Crop
   with a couple of px of padding.

This is exactly what caught the 5 weapons, 6 explosion frames, and 4 smoke
frames automatically. Where items touch or overlap (arena tiles placed
edge-to-edge, ammo/pellet clusters), the auto-pass merges them — those were
cropped by hand instead: overlay a pixel-coordinate grid on the source image,
read off a bounding box by eye, then run the *same* connected-component step
restricted to that sub-region so the final crop is still alpha-tight.

### 2. Character sheets (Player 1 / Player 2)

These are NOT clean cutouts — each pose sits on a soft painted vignette
that fades to transparent at the sheet's outer margins but stays fairly
opaque immediately around the character. Compositing a raw crop onto a
neutral background makes the vignette visible as a soft rectangular card.

Since the game's own arena background is a similar dark navy/purple, the
untouched vignette already blends reasonably — but a mild alpha curve makes
it blend much better:

```python
# a2 = (alpha/255)^gamma, with a hard floor to kill near-zero noise first
a2 = np.where(alpha <= 40, 0, alpha / 255.0) ** 2.2
```

`gamma > 1` pushes low-to-mid alpha down aggressively while barely touching
near-opaque pixels, which tightens the vignette into a much softer glow
without visibly clipping the character's own edges. Applied, then re-cropped
to the tightened alpha's bounding box.

Nine poses were extracted per player this way - `idle`, `run_0/1/2`, `jump`,
`fall`, `crouch`, `hit`, `knockout` - all from the same top row of each
character's sheet (the row without a weapon baked into the pose; the second
row duplicates every pose holding a generic gun, which would double up with
the game's own weapon-attachment sprite, so it's unused). Column x-ranges
were read once off a pixel-coordinate grid overlaid on the sheet and reused
verbatim for player 2 (both sheets share the exact same layout). See
`extract_poses.py` in the offline extraction scratch dir (not part of this
repo) for the exact crop boxes if the pack is regenerated - the short
version: idle x5-95, run x275-538 (3 equal columns), jump x700-790,
fall x790-878, crouch x945-1040, hit x1118-1195, knockout x1332-1428, all
relative to each sheet's own (0,0).

## Mapping to `public/assets/`

| Source group | Extracted as | Notes |
|---|---|---|
| 5 weapon icons | `weapons/weapon_<type>.png` | 1:1, left-to-right order |
| bullet / pellet / rocket / grenade projectile art | `projectiles/projectile_<name>_art.png` | pistol & rifle both use the bullet art in `BootScene` |
| 6 explosion frames | `effects/explosion_0.png` … `_5.png` | left-to-right order = playback order |
| 4 smoke frames | `effects/smoke_0.png` … `_3.png` | picked at random per puff |
| 1 muzzle flash | `effects/muzzle_flash.png` | one representative frame, tinted via additive blend mode in-engine |
| 3 debris pieces (rock/wood/brick) | `effects/debris_0/1/2.png` | picked at random per destroyed tile |
| normal/cracked/broken tile | `arena/tile_normal.png`, `tile_cracked.png`, `tile_broken.png` | swapped by `DestructionSystem` based on remaining tile HP |
| crown/star/flag ×2, skull | `hud/icon_*.png` | crown pair wired into the score HUD; the rest are extracted but not wired into a UI element yet |
| 9 poses × 2 players | `characters/player<N>_<pose>.png` | `idle`, `run_0/1/2`, `jump`, `fall`, `crouch`, `hit`, `knockout` - see above |
