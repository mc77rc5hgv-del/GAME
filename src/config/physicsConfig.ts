/**
 * Central physics tuning. Every "how does it feel" knob lives here so it can be
 * adjusted without touching gameplay systems. Units are Matter.js world units
 * (~1 unit = 1 pixel) unless noted otherwise.
 */
export const PHYSICS_CONFIG = {
  // World
  GRAVITY: 1.55,

  // Player body
  PLAYER_MASS: 6,
  PLAYER_WIDTH: 42,
  PLAYER_HEIGHT: 64,
  PLAYER_FRICTION: 0.01,
  PLAYER_FRICTION_AIR: 0.02,
  PLAYER_RESTITUTION: 0.05,
  // Visual sprite height - deliberately much taller than the collision box
  // (cap/hood/headphones overshoot, plus the character needs to read clearly
  // on screen) and anchored at the feet, not the physics center, so the two
  // can differ freely. See Player.ts for the anchoring.
  PLAYER_SPRITE_HEIGHT: 118,

  // Movement (continuous force applied every tick while a direction is held,
  // integrated by Matter's own force accumulator - same mechanism as gravity)
  MOVE_FORCE: 0.03,
  MAX_SPEED: 8.5,
  AIR_CONTROL: 0.45,
  GROUND_FRICTION: 0.22,
  AIR_FRICTION: 0.985,
  DUCK_SPEED_MULTIPLIER: 0.5,

  // Jump / knockback / recoil / throw below are all *impulses* (J), applied
  // as one-shot velocity changes of magnitude J/mass - i.e. real momentum
  // (p = m*v) rather than a per-tick force. This keeps heavier bodies
  // proportionally harder to move, matching the "weight" the design calls for.
  JUMP_FORCE: 95,
  MAX_JUMPS: 1,
  COYOTE_TIME_MS: 110,
  JUMP_BUFFER_MS: 110,
  FAST_FALL_MULTIPLIER: 1.8,

  // Knockback
  KNOCKBACK_DAMPING: 0.9,
  KNOCKBACK_RECOVERY_MS: 260,
  MIN_KNOCKBACK_STUN_MS: 90,

  // Collisions between players
  PLAYER_PLAYER_RESTITUTION: 0.25,

  // Weapon physics
  WEAPON_MASS: 1.4,
  WEAPON_FRICTION_AIR: 0.015,
  WEAPON_RESTITUTION: 0.35,
  THROW_FORCE: 26,
  THROW_UPWARD_BIAS: -6,
  WEAPON_HIT_DAMAGE: 6,
  WEAPON_HIT_IMPULSE: 18,
  WEAPON_HIT_MIN_SPEED: 4,

  // Explosions (impulses, see above)
  EXPLOSION_FALLOFF_POWER: 2,

  // Arena
  KILL_BOUNDS_MARGIN: 260,

  // Debris
  DEBRIS_FRICTION_AIR: 0.02,
  DEBRIS_RESTITUTION: 0.3,
  DEBRIS_LIFETIME_MS: 6000,
} as const;

export type PhysicsConfig = typeof PHYSICS_CONFIG;
