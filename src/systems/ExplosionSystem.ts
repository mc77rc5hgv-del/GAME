import Phaser from 'phaser';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { distance, explosionFalloff, scaleDisplayToFit } from '../utils/physicsUtils';
import { Player } from '../entities/Player';
import { WeaponPickup } from '../entities/Weapon';
import type { DestructionSystem } from './DestructionSystem';

export interface ExplosionOptions {
  x: number;
  y: number;
  radius: number;
  force: number;
  destructionRadius: number;
  damage: number;
}

export interface ExplosionCallbacks {
  onCameraShake?: (intensity: number, durationMs: number) => void;
  onScreenFlash?: () => void;
}

/**
 * Radial explosion: for every physical object inside `radius`, computes
 * force * falloff(distance) and applies it as an impulse pointing away from
 * the epicenter. Also damages players and destructible terrain, and spawns
 * simple particle/smoke/debris feedback.
 */
export class ExplosionSystem {
  private scene: Phaser.Scene;
  private destruction: DestructionSystem;
  private callbacks: ExplosionCallbacks;

  constructor(scene: Phaser.Scene, destruction: DestructionSystem, callbacks: ExplosionCallbacks = {}) {
    this.scene = scene;
    this.destruction = destruction;
    this.callbacks = callbacks;
  }

  trigger(opts: ExplosionOptions, players: Player[], weapons: WeaponPickup[]): void {
    const { x, y, radius, force, destructionRadius, damage } = opts;

    for (const player of players) {
      if (!player.alive) continue;
      const dist = distance(x, y, player.x, player.y);
      if (dist >= radius) continue;
      const falloff = explosionFalloff(dist, radius, PHYSICS_CONFIG.EXPLOSION_FALLOFF_POWER);
      if (falloff <= 0) continue;
      const dirX = dist > 0.001 ? (player.x - x) / dist : Phaser.Math.FloatBetween(-1, 1);
      const dirY = dist > 0.001 ? (player.y - y) / dist : -1;
      player.applyKnockback(dirX * force * falloff, dirY * force * falloff - force * falloff * 0.15);
      player.takeDamage(damage * falloff);
    }

    for (const weapon of weapons) {
      if (!weapon.body) continue;
      const dist = distance(x, y, weapon.x, weapon.y);
      if (dist >= radius) continue;
      const falloff = explosionFalloff(dist, radius, PHYSICS_CONFIG.EXPLOSION_FALLOFF_POWER);
      if (falloff <= 0) continue;
      const dirX = dist > 0.001 ? (weapon.x - x) / dist : Phaser.Math.FloatBetween(-1, 1);
      const dirY = dist > 0.001 ? (weapon.y - y) / dist : -1;
      const body = weapon.body as MatterJS.BodyType;
      const mass = body.mass || 1;
      weapon.setVelocity(
        body.velocity.x + (dirX * force * falloff) / mass,
        body.velocity.y + (dirY * force * falloff) / mass
      );
    }

    if (destructionRadius > 0) {
      this.destruction.damageInRadius(x, y, destructionRadius, 60);
    }

    this.spawnVisuals(x, y, radius);
    this.callbacks.onCameraShake?.(Phaser.Math.Clamp(radius / 220, 0.3, 1), 260);
    this.callbacks.onScreenFlash?.();
  }

  private spawnVisuals(x: number, y: number, radius: number): void {
    this.spawnExplosionFlipbook(x, y, radius);

    const particleCount = 14;
    for (let i = 0; i < particleCount; i++) {
      const angle = (Math.PI * 2 * i) / particleCount + Phaser.Math.FloatBetween(-0.2, 0.2);
      const speed = Phaser.Math.FloatBetween(60, 220);
      const particle = this.scene.add.circle(
        x,
        y,
        Phaser.Math.Between(2, 5),
        Phaser.Math.RND.pick([0xffcc66, 0xff8844, 0x555555])
      );
      particle.setDepth(49);
      this.scene.tweens.add({
        targets: particle,
        x: x + Math.cos(angle) * speed,
        y: y + Math.sin(angle) * speed - 40,
        alpha: 0,
        duration: Phaser.Math.Between(320, 620),
        ease: 'Cubic.Out',
        onComplete: () => particle.destroy(),
      });
    }

    this.spawnSmoke(x, y, radius);
  }

  /** Steps through the explosion_0..5 stills as a quick hand-timed flipbook. */
  private spawnExplosionFlipbook(x: number, y: number, radius: number): void {
    const frameCount = 6;
    const targetSize = Phaser.Math.Clamp(radius * 1.5, 40, 260);
    const sprite = this.scene.add.sprite(x, y, 'explosion_0');
    sprite.setDepth(50);
    sprite.setBlendMode(Phaser.BlendModes.ADD);
    scaleDisplayToFit(sprite, targetSize);

    const state = { frame: 0 };
    this.scene.tweens.add({
      targets: state,
      frame: frameCount - 1,
      duration: 380,
      ease: 'Linear',
      onUpdate: () => {
        const idx = Math.min(frameCount - 1, Math.floor(state.frame));
        sprite.setTexture(`explosion_${idx}`);
        scaleDisplayToFit(sprite, targetSize);
      },
      onComplete: () => {
        this.scene.tweens.add({
          targets: sprite,
          alpha: 0,
          scaleX: sprite.scaleX * 1.15,
          scaleY: sprite.scaleY * 1.15,
          duration: 180,
          onComplete: () => sprite.destroy(),
        });
      },
    });
  }

  private spawnSmoke(x: number, y: number, radius: number): void {
    const count = Phaser.Math.Clamp(Math.round(radius / 55), 3, 6);
    for (let i = 0; i < count; i++) {
      const key = `smoke_${Phaser.Math.Between(0, 3)}`;
      const smoke = this.scene.add.sprite(x + Phaser.Math.Between(-24, 24), y + Phaser.Math.Between(-20, 10), key);
      smoke.setDepth(48);
      smoke.setAlpha(0.6);
      smoke.setAngle(Phaser.Math.Between(0, 359));
      scaleDisplayToFit(smoke, Phaser.Math.Between(30, 55));
      this.scene.tweens.add({
        targets: smoke,
        y: smoke.y - Phaser.Math.Between(30, 65),
        scaleX: smoke.scaleX * 1.6,
        scaleY: smoke.scaleY * 1.6,
        alpha: 0,
        duration: Phaser.Math.Between(650, 1050),
        ease: 'Cubic.Out',
        onComplete: () => smoke.destroy(),
      });
    }
  }
}
