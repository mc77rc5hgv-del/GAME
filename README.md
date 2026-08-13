# Physics Arena Prototype

A local two-player physics PvP prototype for **Yandex Games**, built as a
gameplay/physics reference for the target experience *"Капибары с пушками 2"*.

This is **stage 1**: the goal is a physically convincing, genuinely playable
arena brawler — movement, weight, knockback, weapons, destruction, rounds —
not final art or a final map. Characters and visuals are deliberately simple
placeholders so the physics and pacing can be compared and tuned first.

## Stack

- **TypeScript** + **Vite** (fast dev server, small production build)
- **Phaser 3** with the **Matter.js** physics plugin (real mass/impulse
  physics, not kinematic movement)
- No backend — the entire core game loop runs client-side in the browser

## Getting started

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build to dist/
npm run preview  # serve the production build locally
npm run test     # unit tests (vitest)
```

`npm run build` runs a strict TypeScript project build (`tsc -b`) before
bundling, so it fails the way CI would on any type error.

## Controls

**Player 1**

| Action | Key |
| --- | --- |
| Move | `A` / `D` |
| Jump | `W` |
| Duck / fast-fall | `S` |
| Pick up / throw weapon | `E` |
| Fire | `R` |

**Player 2**

| Action | Key |
| --- | --- |
| Move | `←` / `→` |
| Jump | `↑` |
| Duck / fast-fall | `↓` |
| Pick up / throw weapon | `L` |
| Fire | `K` |

**Global**

| Action | Key |
| --- | --- |
| Toggle music | `M` |
| Pause | `Esc` |
| Debug overlay | `` ` `` (Backquote) |

All bindings use `KeyboardEvent.code` (physical key position), so a Cyrillic
or any other keyboard layout never breaks controls — `KeyA` is always where
`A` sits on a US QWERTY layout, regardless of the character it types. Arrow
keys and every other mapped game key call `preventDefault()`, so the page
never scrolls, and right-click/text-selection are disabled on the canvas.

### Debug overlay

Press `` ` `` in-game to toggle a debug panel showing FPS, live Matter body
count, per-player velocity/grounded/weapon/ammo state, and Matter collision
bounds drawn directly over every player, weapon, projectile and terrain tile.
This is the primary tool for physics tuning feedback ("jump is too high",
"shotgun recoil is too weak", etc.) — see [Physics tuning](#physics-tuning)
below.

## Gameplay

- Two players spawn on a small destructible arena.
- A round ends when a player's HP reaches 0, or when they fall/are knocked
  past the arena's kill bounds (falling through a destroyed platform counts).
- First to **5 round wins** takes the match.
- Weapons (Pistol, Shotgun, Assault Rifle, Rocket Launcher, Grenade Launcher)
  spawn periodically at fixed points around the arena, each briefly
  telegraphed before appearing. Walk up to one and press the interact key to
  pick it up; press it again to throw your current weapon — thrown weapons
  are real physics objects with a forward impulse and can hit and knock back
  the other player.
- Rocket/grenade explosions apply a radial impulse to players, weapons and
  debris, and can destroy terrain tiles, opening new gaps to fall through.

## Architecture

```
src/
  main.ts                 Boots the Yandex SDK, localization, InputManager,
                           AudioManager, then the Phaser.Game instance.
  config/
    physicsConfig.ts       All movement/jump/knockback/explosion tuning
    gameConfig.ts           Arena size, camera, rounds, spawn timing
    weapons.ts               Per-weapon stats (damage, recoil, spread, ...)
  scenes/
    BootScene.ts            Generates all textures procedurally, then hands
                             off to the menu
    MenuScene.ts             Controls screen + Start button; fires
                             LoadingAPI.ready() once actually interactive
    GameScene.ts              Owns the match: arena, players, systems,
                               collisions, camera, pause, debug overlay
    UIScene.ts                 HUD, round/match banners, pause & match-end
                                overlays - runs in parallel with GameScene
  entities/
    Player.ts                Matter-backed character controller (movement,
                              jump w/ coyote time + buffering, knockback)
    Weapon.ts                 A weapon as a physical world object (ground/
                               thrown state)
    Projectile.ts               Bullets/rockets/grenades
  systems/
    WeaponSystem.ts            Firing, pickup/throw, projectile <-> player/
                                terrain resolution
    ExplosionSystem.ts          Radial impulse + falloff, damage, particles,
                                 camera shake
    DestructionSystem.ts        The arena as small destructible physics
                                 tiles; explosion damage removes real
                                 collision geometry
    RoundManager.ts              Score, round life cycle, slow-mo freeze on
                                  a kill
    SpawnManager.ts               Weapon spawn timers + telegraph
    AudioManager.ts                Procedural WebAudio SFX/music (see below)
    InputManager.ts                 Physical-key input state (P1/P2/global)
  platform/
    YandexSDK.ts              Yandex Games SDK init + safe local-dev mock
  localization/
    en.ts / ru.ts / index.ts  UI strings + language resolution
```

Every physics/weapon constant lives in `config/physicsConfig.ts` and
`config/weapons.ts` so gameplay feel can be retuned by editing numbers in one
place — no system code needs to change for requests like "jump is too high"
or "rocket knockback is too weak".

### Physics model

Movement is force-based (`Player.applyForce` every tick while a direction is
held, damped by ground/air friction when released) rather than snapping
velocity directly, so there's real acceleration, inertia and momentum.
Jumps, recoil, knockback, throws and explosions are all implemented as
**impulses** (`Δv = impulse / mass`) via `utils/physicsUtils.ts#applyImpulse`,
so heavier bodies are proportionally harder to move — real momentum, not an
arbitrary "knockback speed".

## Audio

There are no bundled audio assets yet — `AudioManager` synthesizes every
sound effect and the background pad procedurally via the WebAudio API. The
event-based API (`play('rocket')`, `play('hit')`, `startMusic()`,
`toggleMusic()`, `suspend()`/`resume()`) is the real interface the rest of
the game depends on, so replacing procedural audio with real samples later
only touches this one file. Audio (and gameplay) correctly pause on
`visibilitychange`, window `blur`, and manual pause (`Esc`).

## Yandex Games SDK integration

`index.html` loads the official SDK script
(`https://yandex.ru/games/sdk/v2`). `src/platform/YandexSDK.ts` calls
`YaGames.init()` if it becomes available within ~2.5s; if it never does
(local dev, any non-Yandex hosting), it transparently falls back to an
in-memory mock implementing the same interface, so `npm run dev` always
works standalone with no SDK errors.

**Platform requirement 2.14 (automatic language detection):** the language is
read from `ysdk.environment.i18n.lang` immediately on startup, *before*
anything is rendered (`main.ts` → `initYandexSDK()` → `setLang(...)`) —
`navigator.language` is never used as the source of truth inside the SDK
path (the mock only uses it as a best-effort stand-in since there's no real
SDK to read from locally). Supported languages are `ru` and `en`; every other
SDK language code falls back to `en`. To verify: open the browser console,
you'll see `[YandexSDK:mock] ...` logs confirming the fallback path ran, and
the whole UI (menu, HUD, pause, round banners) renders in the resolved
language — this is covered by `test/localization.test.ts`.

**GameReady:** `ysdk.features.LoadingAPI.ready()` is called exactly once,
from `MenuScene.create()`, only after the menu's full display list (title,
both control columns, Start button) has actually been built — never via a
bare `setTimeout`. To verify: watch the console for the
`[YandexSDK:mock] LoadingAPI.ready()` log and confirm it fires only once the
menu is visible and clickable, with no loading screen left behind.

## Browser lifecycle

`visibilitychange`, window `blur`/`focus` are all wired in `main.ts`: losing
focus suspends the WebAudio context and pauses the Matter world (`Esc` pause
and focus-loss pause are tracked independently, so returning focus doesn't
un-pause a match you paused manually).

## Adaptation

The canvas uses Phaser's `Scale.FIT` mode with `CENTER_BOTH`, so it scales to
fit any viewport/aspect ratio without distorting the arena or HUD. Desktop is
the primary target for this stage. Page scroll, text selection and the
context menu are all disabled over the canvas.

## Physics tuning

Everything gameplay-feel related lives in two files:

- `src/config/physicsConfig.ts` — gravity, mass, friction, move force, max
  speed, jump impulse, knockback damping, explosion falloff power, etc.
- `src/config/weapons.ts` — per-weapon damage, knockback, recoil, spread,
  fire rate, projectile speed, explosion radius/force.

Change a number, save, and `npm run dev` hot-reloads instantly — no other
code needs to change for tuning requests.

## Testing

```bash
npm run test
```

Unit tests (`vitest`) cover the pieces that are pure and meaningful to test
in isolation:

- `test/physicsUtils.test.ts` — explosion falloff curve (epicenter, edge,
  monotonicity, falloff-power sensitivity)
- `test/weapons.test.ts` — weapon configuration sanity (positive stats,
  localized names, only explosive weapons define blast radius/force, etc.)
- `test/localization.test.ts` — SDK language → supported locale resolution
  and fallback (requirement 2.14), and ru/en key-shape parity

Everything else (physics feel, collisions, rendering) was verified by
running the actual game end-to-end in a real browser (movement, jump,
gravity, camera framing, weapon spawn/pickup/fire/throw, damage, knockback,
round death/restart, scoring, pause, debug overlay).

## Known limitations (stage 1)

- Placeholder art: procedurally generated rectangles/circles, not final
  characters or a final map.
- No bundled audio assets yet (see [Audio](#audio)) — SFX/music are
  synthesized.
- Single arena layout; no map selection.
- No online/networked multiplayer — local same-keyboard only, by design for
  this stage.
- Bundle isn't code-split (Phaser itself dominates the bundle size); fine for
  a prototype, worth revisiting before a final production build.
