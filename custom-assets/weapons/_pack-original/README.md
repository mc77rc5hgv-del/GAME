# Pristine pack art (provenance)

Untouched originals, exactly as delivered in
`jumpy_industrial_texture_pack.zip`, for the two items whose sheets were
adjusted afterwards. Kept so the adjustment stays reviewable and can be
redone from source if the pack is revised.

Both adjustments were purely layout inside the atlas cells - no gameplay
code, collider, timing or frame index changed:

- `shock_baton.png` - the pack put every held/swing frame ~32px higher
  inside its 93px-tall cell than Jumpy's own sword art did, so the baton
  floated above the hand rather than sitting in it. Frames 4 (held) and
  8-11 (swing) were shifted down 32px inside their own cells, which puts
  the held frame's content centre back on Jumpy's original y=54.5. Frame 0
  (lying on the ground) already matched and was left alone. Pure
  translation - no rescale, no resample.

- `frag_grenade.png` - content was about half the size of the art it
  replaced, and the three lit-fuse frames (3/4/5) sat at inconsistent
  heights, so the animation jittered. The sheet was rebuilt at 2x tile
  size (50x104 instead of 25x52, same 2x3 grid) with each frame's content
  scaled 2x nearest-neighbour and placed at 2x Jumpy's own per-frame
  content centre. `scripts/apply-weapon-textures.sh` patches the atlas
  `tile_size` to match. Collider (`body_diameter: 15`), fuse time, throw
  velocity and explosion damage are all unchanged - the grenade only
  *draws* twice as large.
