import Phaser from 'phaser';

/**
 * Applies a momentum impulse (J) to a Matter-backed sprite as an instantaneous
 * velocity change of J/mass, i.e. real momentum semantics (p = m*v). Used for
 * jumps, recoil, knockback, throws and explosions - anything that should feel
 * like a sudden hit rather than a sustained push (use body.applyForce for that).
 */
export function applyImpulse(
  sprite: Phaser.Physics.Matter.Sprite,
  impulseX: number,
  impulseY: number
): void {
  const body = sprite.body as MatterJS.BodyType;
  const mass = body.mass || 1;
  sprite.setVelocity(body.velocity.x + impulseX / mass, body.velocity.y + impulseY / mass);
}

export function distance(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}

/**
 * Source art is drawn larger than its in-game footprint (so the engine can
 * downscale for a crisper look), and different art assets don't share a
 * common native resolution. These helpers uniformly scale a sprite/image's
 * *display* size from its actual loaded texture dimensions to hit a target
 * width or height, preserving aspect ratio - independent of whatever the
 * Matter physics body size is set to.
 */
export function scaleDisplayToWidth(
  target: Phaser.GameObjects.Sprite | Phaser.GameObjects.Image,
  width: number
): void {
  const src = target.texture.getSourceImage();
  const scale = width / src.width;
  target.setDisplaySize(width, src.height * scale);
}

/** Uniformly scales so the larger native dimension equals `maxSize`. */
export function scaleDisplayToFit(
  target: Phaser.GameObjects.Sprite | Phaser.GameObjects.Image,
  maxSize: number
): void {
  const src = target.texture.getSourceImage();
  const scale = maxSize / Math.max(src.width, src.height);
  target.setDisplaySize(src.width * scale, src.height * scale);
}

export function scaleDisplayToHeight(
  target: Phaser.GameObjects.Sprite | Phaser.GameObjects.Image,
  height: number
): void {
  const src = target.texture.getSourceImage();
  const scale = height / src.height;
  target.setDisplaySize(src.width * scale, height);
}

/**
 * Radial explosion falloff: 1 at the epicenter, 0 at/beyond radius, using an
 * inverse power curve so the drop-off feels punchy up close and forgiving at
 * the edge. Exported standalone (no Phaser/Matter deps) so it is unit-testable.
 */
export function explosionFalloff(dist: number, radius: number, power: number): number {
  if (radius <= 0) return 0;
  if (dist >= radius) return 0;
  if (dist <= 0) return 1;
  const linear = 1 - dist / radius;
  return Math.pow(linear, power);
}
