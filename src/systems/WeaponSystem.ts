import Phaser from 'phaser';
import { WEAPONS, type WeaponType } from '../config/weapons';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { GAME_CONFIG } from '../config/gameConfig';
import { Player } from '../entities/Player';
import { WeaponPickup } from '../entities/Weapon';
import { Projectile } from '../entities/Projectile';
import { applyImpulse, distance, scaleDisplayToFit } from '../utils/physicsUtils';
import type { ExplosionSystem } from './ExplosionSystem';
import type { AudioManager } from './AudioManager';

const WEAPON_SFX: Record<WeaponType, 'pistol' | 'shotgun' | 'rifle' | 'rocket' | 'grenade'> = {
  pistol: 'pistol',
  shotgun: 'shotgun',
  rifle: 'rifle',
  rocket: 'rocket',
  grenade: 'grenade',
};

export class WeaponSystem {
  private scene: Phaser.Scene;
  private explosionSystem: ExplosionSystem;
  private audio: AudioManager;
  private players: Player[] = [];

  weaponsOnField: WeaponPickup[] = [];
  projectiles: Projectile[] = [];

  constructor(scene: Phaser.Scene, explosionSystem: ExplosionSystem, audio: AudioManager) {
    this.scene = scene;
    this.explosionSystem = explosionSystem;
    this.audio = audio;
  }

  setPlayers(players: Player[]): void {
    this.players = players;
  }

  spawnFieldWeapon(x: number, y: number, type: WeaponType): WeaponPickup {
    const def = WEAPONS[type];
    const weapon = new WeaponPickup(this.scene, x, y, type, def.maxAmmo);
    this.weaponsOnField.push(weapon);
    return weapon;
  }

  removeFieldWeapon(weapon: WeaponPickup): void {
    const idx = this.weaponsOnField.indexOf(weapon);
    if (idx >= 0) this.weaponsOnField.splice(idx, 1);
    weapon.destroy();
  }

  handleInteract(player: Player): void {
    if (!player.alive) return;
    if (player.currentWeapon) {
      this.throwWeapon(player);
    } else {
      this.tryPickup(player);
    }
  }

  private tryPickup(player: Player): void {
    let nearest: WeaponPickup | null = null;
    let nearestDist: number = GAME_CONFIG.WEAPON_INTERACT_RADIUS;
    for (const w of this.weaponsOnField) {
      const d = distance(player.x, player.y, w.x, w.y);
      if (d < nearestDist) {
        nearestDist = d;
        nearest = w;
      }
    }
    if (!nearest) return;
    player.currentWeapon = { type: nearest.weaponType, ammo: nearest.ammo };
    this.removeFieldWeapon(nearest);
    this.audio.play('pickup');
  }

  private throwWeapon(player: Player): void {
    if (!player.currentWeapon) return;
    const { type, ammo } = player.currentWeapon;
    player.currentWeapon = null;

    const spawnX = player.x + PHYSICS_CONFIG.PLAYER_WIDTH * 0.8 * player.facing;
    const spawnY = player.y - 8;
    const weapon = this.spawnFieldWeapon(spawnX, spawnY, type);
    weapon.ammo = ammo;
    weapon.markThrown(player.playerIndex);
    applyImpulse(weapon, PHYSICS_CONFIG.THROW_FORCE * player.facing, PHYSICS_CONFIG.THROW_UPWARD_BIAS);
    this.audio.play('throw');
  }

  tryFire(player: Player, time: number): boolean {
    if (!player.alive || !player.currentWeapon) return false;
    const def = WEAPONS[player.currentWeapon.type];
    if (player.currentWeapon.ammo <= 0) return false;
    if (time - player.lastFireAt < def.fireRateMs) return false;

    player.lastFireAt = time;
    player.currentWeapon.ammo--;

    const muzzle = player.getMuzzlePosition();
    const baseAngle = player.facing === 1 ? 0 : Math.PI;
    for (let i = 0; i < def.projectilesPerShot; i++) {
      const spreadRad = Phaser.Math.DegToRad(Phaser.Math.FloatBetween(-def.spreadDeg / 2, def.spreadDeg / 2));
      const angle = baseAngle + spreadRad;
      const vx = Math.cos(angle) * def.projectileSpeed;
      const vy = Math.sin(angle) * def.projectileSpeed;
      const projectile = new Projectile(this.scene, muzzle.x, muzzle.y, def.type, player.playerIndex, vx, vy);
      this.projectiles.push(projectile);
    }

    player.applyKnockback(-def.recoil * player.facing, -def.recoil * 0.2);
    this.audio.play(WEAPON_SFX[def.type]);
    this.spawnMuzzleFlash(muzzle.x, muzzle.y, player.facing);
    return true;
  }

  private spawnMuzzleFlash(x: number, y: number, facing: 1 | -1): void {
    const flash = this.scene.add.sprite(x, y, 'muzzle_flash');
    flash.setDepth(15);
    flash.setFlipX(facing === -1);
    flash.setBlendMode(Phaser.BlendModes.ADD);
    scaleDisplayToFit(flash, 30);
    flash.setAlpha(0.95);
    this.scene.tweens.add({
      targets: flash,
      alpha: 0,
      scaleX: flash.scaleX * 1.3,
      scaleY: flash.scaleY * 1.3,
      duration: 90,
      onComplete: () => flash.destroy(),
    });
  }

  handleProjectileHitPlayer(projectile: Projectile, player: Player): void {
    if (projectile.exploded || !this.projectiles.includes(projectile)) return;
    if (projectile.ownerIndex === player.playerIndex) return;

    if (projectile.isExplosive) {
      this.explode(projectile);
    } else {
      const dirX = Math.sign(player.x - projectile.x) || player.facing;
      player.takeDamage(projectile.damage);
      player.applyKnockback(dirX * projectile.knockback, -projectile.knockback * 0.35);
      this.audio.play('hit');
    }
    this.removeProjectile(projectile);
  }

  handleProjectileHitTerrain(projectile: Projectile): void {
    if (projectile.exploded || !this.projectiles.includes(projectile)) return;
    if (projectile.isExplosive) {
      this.explode(projectile);
    }
    this.removeProjectile(projectile);
  }

  private explode(projectile: Projectile): void {
    projectile.exploded = true;
    this.explosionSystem.trigger(
      {
        x: projectile.x,
        y: projectile.y,
        radius: projectile.explosionRadius,
        force: projectile.explosionForce,
        destructionRadius: projectile.destructionRadius,
        damage: projectile.damage,
      },
      this.players,
      this.weaponsOnField
    );
    this.audio.play('explosion');
  }

  handleWeaponHitPlayer(weapon: WeaponPickup, player: Player): void {
    if (!weapon.canHit(player.playerIndex)) return;
    const body = weapon.body as MatterJS.BodyType;
    const speed = Math.hypot(body.velocity.x, body.velocity.y);
    if (speed < PHYSICS_CONFIG.WEAPON_HIT_MIN_SPEED) return;

    const dirX = Math.sign(player.x - weapon.x) || 1;
    const dirY = Math.sign(player.y - weapon.y) || -1;
    player.applyKnockback(dirX * PHYSICS_CONFIG.WEAPON_HIT_IMPULSE, dirY * PHYSICS_CONFIG.WEAPON_HIT_IMPULSE * 0.4);
    player.takeDamage(PHYSICS_CONFIG.WEAPON_HIT_DAMAGE);
    this.audio.play('hit');
    weapon.markThrown(weapon.thrownByPlayerIndex ?? player.playerIndex);
  }

  removeProjectile(projectile: Projectile): void {
    const idx = this.projectiles.indexOf(projectile);
    if (idx >= 0) this.projectiles.splice(idx, 1);
    projectile.destroy();
  }

  update(time: number, worldGravityY: number): void {
    for (const projectile of [...this.projectiles]) {
      if (!projectile.body) continue;
      projectile.applyCustomGravity(worldGravityY);
      projectile.syncRotationToVelocity();
      if (time - projectile.spawnedAt > 4500) {
        this.removeProjectile(projectile);
      }
    }
  }

  clear(): void {
    for (const w of [...this.weaponsOnField]) this.removeFieldWeapon(w);
    for (const p of [...this.projectiles]) this.removeProjectile(p);
  }
}
