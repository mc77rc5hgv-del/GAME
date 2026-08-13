import Phaser from 'phaser';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { WEAPONS, type WeaponType } from '../config/weapons';
import { PLAYER_COLORS } from '../entities/Player';

/**
 * Generates every texture procedurally (no binary art assets yet - see the
 * project README for why) and then hands off to MenuScene. Kept intentionally
 * synchronous/instant since there is nothing to actually download.
 */
export class BootScene extends Phaser.Scene {
  constructor() {
    super('BootScene');
  }

  create(): void {
    this.createPlayerTexture('player1', PLAYER_COLORS[1]);
    this.createPlayerTexture('player2', PLAYER_COLORS[2]);

    (Object.keys(WEAPONS) as WeaponType[]).forEach((type) => {
      this.createWeaponTexture(type);
      this.createProjectileTexture(type);
    });

    this.createDebrisTexture();
    this.createPixelTexture();

    this.scene.start('MenuScene');
  }

  private createPlayerTexture(key: string, color: number): void {
    const w = PHYSICS_CONFIG.PLAYER_WIDTH;
    const h = PHYSICS_CONFIG.PLAYER_HEIGHT;
    const g = this.add.graphics();
    g.fillStyle(color, 1);
    g.fillRoundedRect(0, 0, w, h, 8);
    g.lineStyle(2, 0x0a0a12, 1);
    g.strokeRoundedRect(1, 1, w - 2, h - 2, 8);

    // Facing indicator (eye) toward +x, the default facing direction.
    g.fillStyle(0xffffff, 1);
    g.fillCircle(w * 0.68, h * 0.28, 5);
    g.fillStyle(0x0a0a12, 1);
    g.fillCircle(w * 0.7, h * 0.28, 2.4);

    // Simple limb hint so it doesn't read as a pure rectangle.
    g.fillStyle(color, 1);
    g.fillRoundedRect(w * 0.15, h * 0.62, w * 0.7, h * 0.16, 4);

    g.generateTexture(key, w, h);
    g.destroy();
  }

  private createWeaponTexture(type: WeaponType): void {
    const def = WEAPONS[type];
    const w = def.size.width;
    const h = def.size.height;
    const g = this.add.graphics();
    g.fillStyle(def.color, 1);
    g.fillRoundedRect(0, h * 0.25, w * 0.72, h * 0.5, 3);
    g.fillStyle(0x1a1a1a, 1);
    g.fillRoundedRect(0, h * 0.15, w * 0.28, h * 0.7, 3);
    g.fillStyle(def.color, 1);
    g.fillRect(w * 0.6, h * 0.38, w * 0.4, h * 0.24);
    g.generateTexture(`weapon_${type}`, w, h);
    g.destroy();
  }

  private createProjectileTexture(type: WeaponType): void {
    const def = WEAPONS[type];
    const radius = type === 'rocket' ? 9 : type === 'grenade' ? 8 : 4;
    const size = radius * 2 + 2;
    const g = this.add.graphics();
    g.fillStyle(def.color, 1);
    g.fillCircle(size / 2, size / 2, radius);
    if (type === 'rocket' || type === 'grenade') {
      g.fillStyle(0xffffff, 0.6);
      g.fillCircle(size / 2, size / 2, radius * 0.35);
    }
    g.generateTexture(`projectile_${type}`, size, size);
    g.destroy();
  }

  private createDebrisTexture(): void {
    const g = this.add.graphics();
    g.fillStyle(0x5a5266, 1);
    g.fillRect(0, 0, 12, 12);
    g.generateTexture('debris', 12, 12);
    g.destroy();
  }

  private createPixelTexture(): void {
    const g = this.add.graphics();
    g.fillStyle(0xffffff, 1);
    g.fillRect(0, 0, 4, 4);
    g.generateTexture('pixel', 4, 4);
    g.destroy();
  }
}
