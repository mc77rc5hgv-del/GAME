import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { WEAPON_SPAWN_POOL } from '../config/weapons';
import type { WeaponSystem } from './WeaponSystem';

export interface WeaponSpawnPoint {
  x: number;
  y: number;
}

/**
 * Periodically spawns a random weapon at a free spawn point, with a short
 * visual telegraph beforehand. Never spawns on top of a weapon already
 * resting near that point.
 */
export class SpawnManager {
  private scene: Phaser.Scene;
  private weaponSystem: WeaponSystem;
  private points: WeaponSpawnPoint[] = [];
  // -1 = "not yet armed"; armed lazily on the first update() using that call's
  // own `time`, since this.scene.time.now can be stale when reset() is called
  // from create() (Phaser syncs a scene's Clock.now to the first update tick,
  // not to Scene boot time - reading it any earlier returns a stale value).
  private nextSpawnAt = -1;
  private telegraphSprite: Phaser.GameObjects.Arc | null = null;
  private telegraphPoint: WeaponSpawnPoint | null = null;
  private pendingSpawnAt = 0;
  private paused = false;

  constructor(scene: Phaser.Scene, weaponSystem: WeaponSystem) {
    this.scene = scene;
    this.weaponSystem = weaponSystem;
  }

  setPoints(points: WeaponSpawnPoint[]): void {
    this.points = points;
  }

  /** Explicitly re-arms the spawn timer. Only call this with a `time` value
   * known to come from an active update() tick (e.g. a mid-round restart) -
   * never from Scene.create(). */
  reset(time: number): void {
    this.clearTelegraph();
    this.nextSpawnAt = time + GAME_CONFIG.WEAPON_SPAWN.INTERVAL_MS * 0.4;
  }

  setPaused(paused: boolean): void {
    this.paused = paused;
  }

  update(time: number): void {
    if (this.paused || this.points.length === 0) return;

    if (this.nextSpawnAt < 0) {
      this.nextSpawnAt = time + GAME_CONFIG.WEAPON_SPAWN.INTERVAL_MS * 0.4;
      return;
    }

    if (this.telegraphPoint) {
      if (time >= this.pendingSpawnAt) {
        this.doSpawn(this.telegraphPoint);
        this.clearTelegraph();
        this.scheduleNext(time);
      }
      return;
    }

    if (time >= this.nextSpawnAt) {
      if (this.weaponSystem.weaponsOnField.length >= GAME_CONFIG.WEAPON_SPAWN.MAX_ACTIVE_WEAPONS) {
        this.nextSpawnAt = time + 1000;
        return;
      }
      const point = this.pickFreePoint();
      if (!point) {
        this.nextSpawnAt = time + 800;
        return;
      }
      this.startTelegraph(point, time);
    }
  }

  private pickFreePoint(): WeaponSpawnPoint | null {
    const free = this.points.filter(
      (p) => !this.weaponSystem.weaponsOnField.some((w) => Phaser.Math.Distance.Between(p.x, p.y, w.x, w.y) < 60)
    );
    if (free.length === 0) return null;
    return Phaser.Utils.Array.GetRandom(free);
  }

  private startTelegraph(point: WeaponSpawnPoint, time: number): void {
    this.telegraphPoint = point;
    this.pendingSpawnAt = time + GAME_CONFIG.WEAPON_SPAWN.TELEGRAPH_MS;
    this.telegraphSprite = this.scene.add.circle(point.x, point.y, 6, 0xffe066, 0.9);
    this.telegraphSprite.setDepth(3);
    this.scene.tweens.add({
      targets: this.telegraphSprite,
      radius: 22,
      alpha: 0.25,
      duration: GAME_CONFIG.WEAPON_SPAWN.TELEGRAPH_MS,
      ease: 'Sine.InOut',
      onUpdate: (_tween, target: Phaser.GameObjects.Arc) => target.setRadius(target.radius),
    });
  }

  private clearTelegraph(): void {
    if (this.telegraphSprite) {
      this.scene.tweens.killTweensOf(this.telegraphSprite);
      this.telegraphSprite.destroy();
    }
    this.telegraphSprite = null;
    this.telegraphPoint = null;
  }

  private doSpawn(point: WeaponSpawnPoint): void {
    const type = Phaser.Utils.Array.GetRandom(WEAPON_SPAWN_POOL);
    this.weaponSystem.spawnFieldWeapon(point.x, point.y, type);
  }

  private scheduleNext(time: number): void {
    this.nextSpawnAt =
      time + GAME_CONFIG.WEAPON_SPAWN.INTERVAL_MS + Phaser.Math.Between(0, GAME_CONFIG.WEAPON_SPAWN.INTERVAL_JITTER_MS);
  }
}
