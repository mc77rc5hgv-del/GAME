import Phaser from 'phaser';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { GAME_CONFIG } from '../config/gameConfig';
import { WEAPONS, type WeaponType } from '../config/weapons';
import { scaleDisplayToWidth } from '../utils/physicsUtils';

/**
 * A weapon lying/flying in the world as a physical object (on the ground,
 * freshly spawned, or thrown by a player). Picking it up destroys this
 * instance and moves its state onto Player.currentWeapon; throwing spawns a
 * new one back into the world with an outward impulse.
 */
export class WeaponPickup extends Phaser.Physics.Matter.Sprite {
  weaponType: WeaponType;
  ammo: number;
  thrownByPlayerIndex: 1 | 2 | null = null;
  thrownAt = 0;
  spawnedAt: number;
  private shadow: Phaser.GameObjects.Ellipse;

  constructor(scene: Phaser.Scene, x: number, y: number, weaponType: WeaponType, ammo: number) {
    super(scene.matter.world, x, y, `weapon_${weaponType}`, undefined, {
      label: `weapon_${weaponType}`,
    });
    this.weaponType = weaponType;
    this.ammo = ammo;
    this.spawnedAt = scene.time.now;
    scene.add.existing(this);

    const def = WEAPONS[weaponType];
    this.setRectangle(def.size.width, def.size.height, { chamfer: { radius: 3 } });
    this.setMass(PHYSICS_CONFIG.WEAPON_MASS);
    this.setFriction(0.4, undefined, PHYSICS_CONFIG.WEAPON_FRICTION_AIR);
    this.setBounce(PHYSICS_CONFIG.WEAPON_RESTITUTION);
    this.setCollisionCategory(GAME_CONFIG.COLLISION.WEAPON);
    this.setCollidesWith([
      GAME_CONFIG.COLLISION.GROUND,
      GAME_CONFIG.COLLISION.WEAPON,
      GAME_CONFIG.COLLISION.PLAYER,
      GAME_CONFIG.COLLISION.DEBRIS,
    ]);
    this.setDepth(5);
    scaleDisplayToWidth(this, def.size.width * 1.8);

    this.shadow = scene.add.ellipse(x, y, def.size.width * 1.3, 6, 0x000000, 0.3);
    this.shadow.setDepth(2);
  }

  /** Keeps the ground shadow under the weapon as it slides/bounces. */
  syncShadow(): void {
    this.shadow.setPosition(this.x, this.y + 10);
  }

  markThrown(byPlayerIndex: 1 | 2): void {
    this.thrownByPlayerIndex = byPlayerIndex;
    this.thrownAt = this.scene.time.now;
  }

  /** Thrown weapons can hit their thrower again once this much time has passed. */
  canHit(playerIndex: 1 | 2): boolean {
    if (this.thrownByPlayerIndex !== playerIndex) return true;
    return this.scene.time.now - this.thrownAt > 220;
  }

  destroy(fromScene?: boolean): void {
    this.shadow.destroy();
    super.destroy(fromScene);
  }
}
