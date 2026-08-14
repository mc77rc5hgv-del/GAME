#!/usr/bin/env python3
"""Offline authoring tool: regenerates three corrected weapon sheets from the
pristine pack art in custom-assets/weapons/_pack-original/.

NOT part of the game build - contributors never need to run this, and it is
deliberately kept out of scripts/fetch-dev-assets.sh so that the player-facing
pipeline stays python-free (see that script's header). Its outputs are
committed. Re-running it is idempotent: it always rebuilds from _pack-original,
never from its own output.

Requires: pillow, numpy, scipy.

Why each item needs fixing - all three are cases where the pack art is laid out
differently inside the atlas cell than Jumpy's own art was, while every bit of
gameplay tuning (grab_offset, fin_offset, damage regions, frame indices,
colliders) was authored against Jumpy's layout. So the art is moved/scaled to
sit where the mechanics already expect it, rather than retuning the mechanics.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

PACK = "/home/user/GAME/custom-assets/weapons"
SRC = f"{PACK}/_pack-original"


def cells(im, tw, th, cols):
    rows = im.height // th
    for idx in range(rows * cols):
        r, c = divmod(idx, cols)
        yield idx, r, c, im.crop((c * tw, r * th, (c + 1) * tw, (r + 1) * th))


def drop_specks(cell, keep_ratio=0.2):
    """Remove detached blobs far smaller than the frame's main shape.

    The pack's grenade frames each carry a stray ~10%-of-body sliver floating
    off to one side, which reads in game as a few black pixels hanging in the
    air next to the grenade. Jumpy's own idle grenade frame is a single
    connected shape, so nothing legitimate is lost here.
    """
    a = np.array(cell)
    lbl, n = ndimage.label(a[:, :, 3] > 10, structure=np.ones((3, 3)))
    if n <= 1:
        return cell, 0
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
    biggest = sizes.max()
    removed = 0
    for i, size in enumerate(sizes, start=1):
        if size < biggest * keep_ratio:
            a[lbl == i] = (0, 0, 0, 0)
            removed += int(size)
    return Image.fromarray(a), removed


def place(dst, piece, tw, th, r, c, centre, label):
    x = c * tw + centre[0] - piece.width // 2
    y = r * th + centre[1] - piece.height // 2
    assert c * tw <= x and x + piece.width <= (c + 1) * tw, f"{label}: x overflow"
    assert r * th <= y and y + piece.height <= (r + 1) * th, f"{label}: y overflow"
    dst.paste(piece, (x, y))


# ---------------------------------------------------------------- sword ---
# 4x3 grid of 65x93. Frames the game uses: 0 = lying on ground, 4 = held/idle,
# 8..11 = the swing. Every held/swing frame was drawn ~32px higher in its cell
# than Jumpy's sword, so the baton floated above the hand. Frame 0 already
# matched Jumpy's centre and is left untouched. Pure translation - no resample.
SWORD_TW, SWORD_TH, SWORD_COLS = 65, 93, 4
SWORD_SHIFT, SWORD_FRAMES = 32, {4, 8, 9, 10, 11}

sw = Image.open(f"{SRC}/shock_baton.png").convert("RGBA")
out = Image.new("RGBA", sw.size, (0, 0, 0, 0))
for idx, r, c, cell in cells(sw, SWORD_TW, SWORD_TH, SWORD_COLS):
    bbox = cell.getbbox()
    if bbox is None:
        continue
    if idx in SWORD_FRAMES:
        piece = cell.crop(bbox)
        shifted = Image.new("RGBA", (SWORD_TW, SWORD_TH), (0, 0, 0, 0))
        assert bbox[1] + SWORD_SHIFT + piece.height <= SWORD_TH, f"sword {idx} overflow"
        shifted.paste(piece, (bbox[0], bbox[1] + SWORD_SHIFT))
        cell = shifted
    out.paste(cell, (c * SWORD_TW, r * SWORD_TH))
out.save(f"{PACK}/shock_baton/shock_baton.png")
print(f"shock_baton : frames {sorted(SWORD_FRAMES)} shifted down {SWORD_SHIFT}px")

# -------------------------------------------------------------- grenade ---
# 3x2 grid. Rebuilt at 2x tile size (25x52 -> 50x104) with content scaled 2x,
# because the pack drew the grenade about half the size of the art it replaced
# and it was unreadable in game. Each frame is placed on Jumpy's own per-frame
# content centre, doubled - which also fixes the pack's frames 3/4/5 sitting at
# three different heights and jittering through the lit-fuse animation.
# Stray specks are dropped on the way through.
GR_COLS, GR_TW, GR_TH = 3, 25, 52
GR_NEW_TW, GR_NEW_TH = GR_TW * 2, GR_TH * 2
GR_CENTRES = {0: (25, 46), 3: (27, 37), 4: (27, 34), 5: (29, 37)}

gr = Image.open(f"{SRC}/frag_grenade.png").convert("RGBA")
new = Image.new("RGBA", (GR_NEW_TW * GR_COLS, GR_NEW_TH * 2), (0, 0, 0, 0))
total_removed = 0
for idx, r, c, cell in cells(gr, GR_TW, GR_TH, GR_COLS):
    if idx not in GR_CENTRES:
        continue
    cell, removed = drop_specks(cell)
    total_removed += removed
    bbox = cell.getbbox()
    assert bbox is not None, f"grenade {idx} empty after speck removal"
    piece = cell.crop(bbox)
    piece = piece.resize((piece.width * 2, piece.height * 2), Image.NEAREST)
    place(new, piece, GR_NEW_TW, GR_NEW_TH, r, c, GR_CENTRES[idx], f"grenade {idx}")
new.save(f"{PACK}/frag_grenade/frag_grenade.png")
print(f"frag_grenade: rebuilt {new.size}, tile {GR_NEW_TW}x{GR_NEW_TH}, "
      f"{total_removed}px of stray specks removed")

# ------------------------------------------------------------- canister ---
# 3x2 grid of 32x63. Two separate problems:
#   * frames 0/3 (idle + lit) were drawn 45px tall against a 26-unit collider
#     and Jumpy's own 32px art - visually oversized, so scaled to 0.8.
#   * frames 4/5 (the rest of the lit animation, kick_bomb.yaml lit_frames
#     3..5) were drawn at roughly half the scale of frames 0/3, so the lit
#     canister strobed between two very different sizes 8 times a second.
#     Scaled up to sit in the same visual weight class as 0/3.
# Centres are Jumpy's own, so grab_offset [5,-2] keeps working unchanged.
KB_COLS, KB_TW, KB_TH = 3, 32, 63
KB_FRAMES = {  # idx: (scale, centre)
    0: (0.80, (16, 29)),
    3: (0.80, (16, 23)),
    4: (1.30, (16, 22)),
    5: (1.30, (16, 24)),
}

kb = Image.open(f"{SRC}/explosive_canister.png").convert("RGBA")
out = Image.new("RGBA", kb.size, (0, 0, 0, 0))
for idx, r, c, cell in cells(kb, KB_TW, KB_TH, KB_COLS):
    if idx not in KB_FRAMES:
        continue
    scale, centre = KB_FRAMES[idx]
    bbox = cell.getbbox()
    assert bbox is not None, f"canister {idx} empty"
    piece = cell.crop(bbox)
    piece = piece.resize(
        (max(1, round(piece.width * scale)), max(1, round(piece.height * scale))),
        Image.NEAREST,
    )
    place(out, piece, KB_TW, KB_TH, r, c, centre, f"canister {idx}")
out.save(f"{PACK}/explosive_canister/explosive_canister.png")
print("explosive_canister: frames 0/3 scaled 0.80, frames 4/5 scaled 1.30")
