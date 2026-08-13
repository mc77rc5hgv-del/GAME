import Phaser from 'phaser';
import { t } from '../localization';

const CHARACTERS: [string, string][] = [
  ['player1', 'assets/characters/player1_idle.png'],
  ['player2', 'assets/characters/player2_idle.png'],
];

const WEAPONS_ART: [string, string][] = [
  ['weapon_pistol', 'assets/weapons/weapon_pistol.png'],
  ['weapon_shotgun', 'assets/weapons/weapon_shotgun.png'],
  ['weapon_rifle', 'assets/weapons/weapon_rifle.png'],
  ['weapon_rocket', 'assets/weapons/weapon_rocket.png'],
  ['weapon_grenade', 'assets/weapons/weapon_grenade.png'],
];

// Only 4 distinct projectile designs exist (pistol and rifle share a bullet
// tracer) - mapped onto the 5 weapon types Projectile expects a texture for.
const PROJECTILES_ART: [string, string][] = [
  ['projectile_pistol', 'assets/projectiles/projectile_bullet_art.png'],
  ['projectile_rifle', 'assets/projectiles/projectile_bullet_art.png'],
  ['projectile_shotgun', 'assets/projectiles/projectile_pellet_art.png'],
  ['projectile_rocket', 'assets/projectiles/projectile_rocket_art.png'],
  ['projectile_grenade', 'assets/projectiles/projectile_grenade_art.png'],
];

const EFFECTS_ART: [string, string][] = [
  ['muzzle_flash', 'assets/effects/muzzle_flash.png'],
  ['debris_0', 'assets/effects/debris_0.png'],
  ['debris_1', 'assets/effects/debris_1.png'],
  ['debris_2', 'assets/effects/debris_2.png'],
  ['explosion_0', 'assets/effects/explosion_0.png'],
  ['explosion_1', 'assets/effects/explosion_1.png'],
  ['explosion_2', 'assets/effects/explosion_2.png'],
  ['explosion_3', 'assets/effects/explosion_3.png'],
  ['explosion_4', 'assets/effects/explosion_4.png'],
  ['explosion_5', 'assets/effects/explosion_5.png'],
  ['smoke_0', 'assets/effects/smoke_0.png'],
  ['smoke_1', 'assets/effects/smoke_1.png'],
  ['smoke_2', 'assets/effects/smoke_2.png'],
  ['smoke_3', 'assets/effects/smoke_3.png'],
];

const ARENA_ART: [string, string][] = [
  ['tile_normal', 'assets/arena/tile_normal.png'],
  ['tile_cracked', 'assets/arena/tile_cracked.png'],
  ['tile_broken', 'assets/arena/tile_broken.png'],
];

const HUD_ART: [string, string][] = [
  ['icon_crown_p1', 'assets/hud/icon_crown_p1.png'],
  ['icon_crown_p2', 'assets/hud/icon_crown_p2.png'],
  ['icon_star_p1', 'assets/hud/icon_star_p1.png'],
  ['icon_star_p2', 'assets/hud/icon_star_p2.png'],
  ['icon_flag_p1', 'assets/hud/icon_flag_p1.png'],
  ['icon_flag_p2', 'assets/hud/icon_flag_p2.png'],
  ['icon_skull', 'assets/hud/icon_skull.png'],
];

const ALL_ART = [...CHARACTERS, ...WEAPONS_ART, ...PROJECTILES_ART, ...EFFECTS_ART, ...ARENA_ART, ...HUD_ART];

/**
 * Loads the real texture pack (see /public/assets) and hands off to
 * MenuScene. The pack's source sheets are presentation collages, not clean
 * per-frame exports - extraction/cropping/alpha cleanup happened offline
 * (see project notes); this scene just loads the already-processed PNGs.
 */
export class BootScene extends Phaser.Scene {
  private loadingText!: Phaser.GameObjects.Text;

  constructor() {
    super('BootScene');
  }

  preload(): void {
    const { width, height } = this.scale;
    this.cameras.main.setBackgroundColor(0x14101d);
    this.loadingText = this.add
      .text(width / 2, height / 2, t().menu.loading, {
        fontFamily: 'monospace',
        fontSize: '20px',
        color: '#8a83a8',
      })
      .setOrigin(0.5);

    for (const [key, path] of ALL_ART) {
      this.load.image(key, path);
    }

    this.load.on('progress', (fraction: number) => {
      this.loadingText.setText(`${t().menu.loading} ${Math.round(fraction * 100)}%`);
    });

    this.createPixelTexture();
  }

  create(): void {
    this.loadingText.destroy();
    this.scene.start('MenuScene');
  }

  private createPixelTexture(): void {
    const g = this.add.graphics();
    g.fillStyle(0xffffff, 1);
    g.fillRect(0, 0, 4, 4);
    g.generateTexture('pixel', 4, 4);
    g.destroy();
  }
}
