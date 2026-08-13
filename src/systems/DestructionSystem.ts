import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { distance, scaleDisplayToFit } from '../utils/physicsUtils';

export interface TileRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface DestructibleTile {
  id: number;
  body: MatterJS.BodyType;
  /** Only exists once a tile takes damage - undamaged tiles are covered by
   * the platform's unified slab, not their own sprite (that's what keeps a
   * solid platform from reading as a grid of identical squares). */
  gfx: Phaser.GameObjects.Image | null;
  hp: number;
  maxHp: number;
  x: number;
  y: number;
}

const TILE_SIZE = 40;
const TILE_HP = 34;
const DEBRIS_TEXTURES = ['debris_0', 'debris_1', 'debris_2'];
const VOID_COLOR = 0x0f0c18;
const SLAB_FILL = 0x494c63;
const SLAB_TOP = 0x666a86;
const SLAB_BOTTOM = 0x2c2c40;
const SLAB_OUTLINE = 0x201f30;
let nextTileId = 1;

function tileTextureFor(ratio: number): string {
  if (ratio > 0.5) return 'tile_normal';
  if (ratio > 0.2) return 'tile_cracked';
  return 'tile_broken';
}

/**
 * Builds the arena out of small destructible physics tiles (unchanged, one
 * static body per TILE_SIZE cell - explosions still remove real collision
 * geometry), but renders each platform as ONE unified slab shape instead of
 * one bordered sprite per cell. Individual tile art only appears once a
 * specific cell is actually damaged; destroyed cells punch a visible hole
 * through the slab.
 */
export class DestructionSystem {
  private scene: Phaser.Scene;
  private tiles = new Map<number, DestructibleTile>();
  private debris: Phaser.Physics.Matter.Image[] = [];
  private slabs: Phaser.GameObjects.Graphics[] = [];
  private holes: Phaser.GameObjects.Rectangle[] = [];
  private tileGroup = GAME_CONFIG.COLLISION.GROUND;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /** Fills every TILE_SIZE cell inside each rect with a destructible tile,
   * plus one unified visual slab per rect drawn underneath them. */
  buildFromRects(rects: TileRect[]): void {
    this.clear();
    for (const rect of rects) {
      this.drawSlab(rect);
      const cols = Math.round(rect.width / TILE_SIZE);
      const rows = Math.round(rect.height / TILE_SIZE);
      const startX = rect.x - rect.width / 2 + TILE_SIZE / 2;
      const startY = rect.y - rect.height / 2 + TILE_SIZE / 2;
      for (let cy = 0; cy < rows; cy++) {
        for (let cx = 0; cx < cols; cx++) {
          this.addTile(startX + cx * TILE_SIZE, startY + cy * TILE_SIZE);
        }
      }
    }
  }

  private drawSlab(rect: TileRect): void {
    const g = this.scene.add.graphics();
    const w = rect.width;
    const h = rect.height;
    const left = rect.x - w / 2;
    const top = rect.y - h / 2;
    const radius = 10;

    g.fillStyle(SLAB_FILL, 1);
    g.fillRoundedRect(left, top, w, h, radius);

    // Top highlight band - reads as the walkable surface catching light.
    const topBandH = Math.min(12, h * 0.3);
    g.fillStyle(SLAB_TOP, 1);
    g.fillRoundedRect(left, top, w, topBandH, { tl: radius, tr: radius, bl: 0, br: 0 });

    // Bottom shading band - gives the block a sense of depth/thickness.
    const bottomBandH = Math.min(10, h * 0.22);
    g.fillStyle(SLAB_BOTTOM, 1);
    g.fillRoundedRect(left, top + h - bottomBandH, w, bottomBandH, { tl: 0, tr: 0, bl: radius, br: radius });

    g.lineStyle(2, SLAB_OUTLINE, 1);
    g.strokeRoundedRect(left + 1, top + 1, w - 2, h - 2, radius);

    g.setDepth(0);
    this.slabs.push(g);
  }

  private addTile(x: number, y: number): void {
    const id = nextTileId++;
    const body = this.scene.matter.add.rectangle(x, y, TILE_SIZE, TILE_SIZE, {
      isStatic: true,
      label: `tile_${id}`,
      friction: 0.35,
      collisionFilter: {
        category: this.tileGroup,
        mask: 0xffffffff,
      },
    });
    this.tiles.set(id, { id, body, gfx: null, hp: TILE_HP, maxHp: TILE_HP, x, y });
  }

  getAllBodies(): MatterJS.BodyType[] {
    return Array.from(this.tiles.values()).map((t) => t.body);
  }

  /** Applies explosion damage/destruction to every tile within radius. */
  damageInRadius(cx: number, cy: number, radius: number, maxDamage: number): void {
    for (const tile of Array.from(this.tiles.values())) {
      const dist = distance(cx, cy, tile.x, tile.y);
      if (dist >= radius) continue;
      const falloff = 1 - dist / radius;
      const dmg = maxDamage * falloff;
      this.damageTile(tile, dmg);
    }
  }

  private damageTile(tile: DestructibleTile, dmg: number): void {
    tile.hp -= dmg;
    const ratio = Phaser.Math.Clamp(tile.hp / tile.maxHp, 0, 1);
    const textureKey = tileTextureFor(ratio);
    if (!tile.gfx) {
      tile.gfx = this.scene.add.image(tile.x, tile.y, textureKey);
      tile.gfx.setDisplaySize(TILE_SIZE, TILE_SIZE);
      tile.gfx.setDepth(1);
    } else if (tile.gfx.texture.key !== textureKey) {
      tile.gfx.setTexture(textureKey);
      tile.gfx.setDisplaySize(TILE_SIZE, TILE_SIZE);
    }
    if (tile.hp <= 0) {
      this.destroyTile(tile);
    }
  }

  private destroyTile(tile: DestructibleTile): void {
    this.tiles.delete(tile.id);
    this.scene.matter.world.remove(tile.body);
    tile.gfx?.destroy();
    this.punchHole(tile.x, tile.y);
    this.spawnDebris(tile.x, tile.y);
  }

  /** Covers the destroyed cell so the slab underneath doesn't show through
   * as solid where a tile used to be. */
  private punchHole(x: number, y: number): void {
    const hole = this.scene.add.rectangle(x, y, TILE_SIZE, TILE_SIZE, VOID_COLOR, 1);
    hole.setDepth(1);
    this.holes.push(hole);
  }

  private spawnDebris(x: number, y: number): void {
    const count = 2;
    for (let i = 0; i < count; i++) {
      const size = Phaser.Math.Between(7, 14);
      const debris = this.scene.matter.add.image(
        x + Phaser.Math.Between(-10, 10),
        y + Phaser.Math.Between(-10, 10),
        Phaser.Utils.Array.GetRandom(DEBRIS_TEXTURES)
      );
      debris.setRectangle(size, size);
      scaleDisplayToFit(debris, size);
      debris.setFrictionAir(PHYSICS_CONFIG.DEBRIS_FRICTION_AIR);
      debris.setBounce(PHYSICS_CONFIG.DEBRIS_RESTITUTION);
      debris.setCollisionCategory(GAME_CONFIG.COLLISION.DEBRIS);
      debris.setCollidesWith([GAME_CONFIG.COLLISION.GROUND, GAME_CONFIG.COLLISION.DEBRIS]);
      debris.setVelocity(Phaser.Math.Between(-4, 4), Phaser.Math.Between(-6, -1));
      debris.setAngularVelocity(Phaser.Math.FloatBetween(-0.2, 0.2));
      debris.setDepth(4);
      this.scene.time.delayedCall(PHYSICS_CONFIG.DEBRIS_LIFETIME_MS, () => {
        debris.destroy();
        const idx = this.debris.indexOf(debris);
        if (idx >= 0) this.debris.splice(idx, 1);
      });
      this.debris.push(debris);
    }
  }

  clear(): void {
    for (const tile of this.tiles.values()) {
      this.scene.matter.world.remove(tile.body);
      tile.gfx?.destroy();
    }
    this.tiles.clear();
    for (const slab of this.slabs) slab.destroy();
    this.slabs = [];
    for (const hole of this.holes) hole.destroy();
    this.holes = [];
    for (const d of this.debris) d.destroy();
    this.debris = [];
  }

  get tileCount(): number {
    return this.tiles.size;
  }
}
