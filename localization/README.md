# Localization

Original English and Russian UI text for this project, written from
scratch (not copied from Fish Folk: Jumpy's own locale files, which are
excluded per `THIRD_PARTY_NOTICES.md`). Files are named and keyed to match
the Fluent (`.ftl`) resources Jumpy's own UI code already looks up, so no
Rust code needs to change to use them - only the game-data files that
aren't committed to this repo (see below).

`en/` and `ru/` only cover the UI surfaces this project actually ships
(main menu, player select, map select, scoring, settings, controls).
Jumpy's dev-only/editor/networking screens are intentionally not
translated, since this project doesn't use them.

## How this gets loaded today

Jumpy's own `assets/game.yaml` (fetched locally and gitignored - see
`scripts/fetch-dev-assets.sh`) is what actually wires a `locales/` folder
into the running game, and that whole file is excluded from this repo for
the same CC BY-NC reasons as the rest of `assets/`. Until this project has
its own from-scratch `game.yaml` (planned alongside the eventual custom-art
swap), `fetch-dev-assets.sh` copies `ru/` into the fetched
`assets/locales/ru-RU/` and registers it, purely for local testing of the
Yandex language bridge (`src/yandex.rs`, `wasm_resources/index.html`).
