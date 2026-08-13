import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { WEAPONS, type WeaponType } from '../config/weapons';

export class Projectile extends Phaser.Physics.Matter.Sprite {
  weaponType: WeaponType;
  ownerIndex: 1 | 2;
  damage: number;
  knockback: number;
  explosionRadius: number;
  explosionForce: number;
  destructionRadius: number;
  isExplosive: boolean;
  spawnedAt: number;
  exploded = false;
  private gravityScale = 0;

  constructor(
    scene: Phaser.Scene,
    x: number,
    y: number,
    weaponType: WeaponType,
    ownerIndex: 1 | 2,
    velocityX: number,
    velocityY: number
  ) {
    const def = WEAPONS[weaponType];
    super(scene.matter.world, x, y, `projectile_${weaponType}`, undefined, {
      label: `projectile_${weaponType}`,
      isSensor: true,
    });
    this.weaponType = weaponType;
    this.ownerIndex = ownerIndex;
    this.damage = def.damage;
    this.knockback = def.knockback;
    this.explosionRadius = def.explosionRadius;
    this.explosionForce = def.explosionForce;
    this.destructionRadius = def.destructionRadius;
    this.isExplosive = def.explosionRadius > 0;
    this.spawnedAt = scene.time.now;
    scene.add.existing(this);

    const radius = weaponType === 'rocket' ? 9 : weaponType === 'grenade' ? 8 : 4;
    this.setCircle(radius);
    this.setFrictionAir(0);
    this.setMass(0.15);
    this.setFixedRotation();
    this.setCollisionCategory(GAME_CONFIG.COLLISION.PROJECTILE);
    this.setCollidesWith([GAME_CONFIG.COLLISION.GROUND, GAME_CONFIG.COLLISION.PLAYER, GAME_CONFIG.COLLISION.DEBRIS]);
    this.setVelocity(velocityX, velocityY);
    this.setDepth(6);

    // Native Matter/Phaser gravity is all-or-nothing per body; we want partial
    // scales (e.g. a grenade arcs more than a shotgun pellet), so gravity is
    // disabled at the engine level and re-applied manually in update().
    super.setIgnoreGravity(true);
    this.gravityScale = def.projectileGravityScale;
  }

  /** Called every physics step from GameScene with the world's gravity.y. */
  applyCustomGravity(worldGravityY: number): void {
    if (this.gravityScale <= 0) return;
    const body = this.body as MatterJS.BodyType;
    this.applyForce(new Phaser.Math.Vector2(0, worldGravityY * 0.001 * this.gravityScale * body.mass));
  }

  syncRotationToVelocity(): void {
    const body = this.body as MatterJS.BodyType;
    if (body.velocity.x !== 0 || body.velocity.y !== 0) {
      this.rotation = Math.atan2(body.velocity.y, body.velocity.x);
    }
  }
}
