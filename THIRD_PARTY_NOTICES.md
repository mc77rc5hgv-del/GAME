# Third-Party Notices

This project's gameplay foundation is forked from **Fish Folk: Jumpy**
(https://github.com/fishfolk/jumpy), built on the **Bones** framework
(https://github.com/fishfolk/bones). This document records what was taken,
under what license, and what was deliberately excluded.

## Code — used, permitted

| Component | Source | License | Notes |
|---|---|---|---|
| Jumpy source code (`src/`, `book/`, `contrib/`, `scripts/`, `wasm_resources/`, build config) | https://github.com/fishfolk/jumpy | MIT OR Apache-2.0 (dual, at your option) | Copyright (c) The Fish Fight Game & Spicy Lobster Developers. License text preserved in `licenses/LICENSE-MIT` and `licenses/LICENSE-APACHE`, and in `LICENSE`. |
| Bones engine (`bones_framework`, `bones_bevy_renderer`) | https://github.com/fishfolk/bones | MIT OR Apache-2.0 (dual) | Pulled as a normal Cargo git dependency in `Cargo.toml`, exactly as upstream Jumpy does. Not vendored into this repo. |
| Full transitive crate dependency tree (Bevy, rapier2d, wgpu, wasm-bindgen, etc.) | crates.io / GitHub | Verified permissive (MIT, Apache-2.0, BSD-2/3-Clause, MPL-2.0, Zlib, CC0-1.0, etc.) | Independently corroborated by Jumpy's own `deny.toml`, which allow-lists only permissive licenses and restricts git dependencies to `dimforge/rapier` and `gschup/ggrs`, plus the `fishfolk` GitHub org. |

Both MIT and Apache-2.0 require preserving copyright and license notices in
redistributions. `LICENSE`, `licenses/LICENSE-MIT`, `licenses/LICENSE-APACHE`,
and `CREDITS.md` are carried over unmodified for this reason.

## Media assets — NOT used, excluded

Jumpy's own game assets (`assets/`, `old_assets/` in the upstream repo —
sprite sheets, audio, fonts, and the yaml level/metadata files bundled with
them) are:

> Copyright (c) 2020-2024 The Fish Folk Game & Spicy Lobster Developers,
> licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

CC BY-NC is **non-commercial only**. Yandex Games is a monetized (ad-funded)
platform, so shipping these assets there is not permitted. Consequently:

- **None of Jumpy's own assets are committed to this repository.**
- `assets/` is listed in `.gitignore`. `scripts/fetch-dev-assets.sh` can pull
  them locally, on demand, strictly for non-commercial baseline gameplay
  testing during development (verifying movement/physics/weapons/maps work
  before any custom content is wired in). They must never appear in a build
  that is deployed publicly or submitted to Yandex Games.
- Before any real release, all in-game art/audio must come from
  `legacy-assets/physics-arena-texture-pack/` (the project's own
  AI-generated texture pack, extracted from the original Phaser prototype —
  see `legacy-assets/asset-pipeline.md`) or other properly licensed/original
  content.

## Deliberately not ported

- `steam/` — Steam-specific packaging, irrelevant to a Yandex Games browser target.
- `.github/workflows/` — Jumpy's own CI (Steam builds, itch.io deploys, GitHub Pages demo). This repo will get its own CI suited to a Yandex Games web build instead.
- `PACKAGING.md`, distro packaging (Arch `pacman`, launcher) — desktop distribution mechanisms not applicable to a browser-only target.
- `docs/` (Jumpy's top-level docs folder, distinct from this repo's own `docs/`) — internal contributor docs not relevant to this fork; `book/` (the user-facing game/mod-authoring manual) was kept since it documents the architecture this project builds on.

## Attribution

Original Fish Folk: Jumpy credits are preserved verbatim in `CREDITS.md`.
