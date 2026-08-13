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
  gfx: Phaser.GameObjects.Image;
  hp: number;
  maxHp: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

const TILE_SIZE = 40;
const TILE_HP = 34;
const DEBRIS_TEXTURES = ['debris_0', 'debris_1', 'debris_2'];
let nextTileId = 1;

function tileTextureFor(ratio: number): string {
  if (ratio > 0.5) return 'tile_normal';
  if (ratio > 0.2) return 'tile_cracked';
  return 'tile_broken';
}

/**
 * Builds the arena entirely out of small destructible physics tiles so
 * destruction changes real collision geometry (not just decoration), and
 * owns damaging/removing tiles when explosions or rockets hit them.
 */
export class DestructionSystem {
  private scene: Phaser.Scene;
  private tiles = new Map<number, DestructibleTile>();
  private debris: Phaser.Physics.Matter.Image[] = [];
  private tileGroup = GAME_CONFIG.COLLISION.GROUND;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /** Fills every TILE_SIZE cell inside each rect with a destructible tile. */
  buildFromRects(rects: TileRect[]): void {
    this.clear();
    for (const rect of rects) {
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
    const gfx = this.scene.add.image(x, y, 'tile_normal');
    gfx.setDisplaySize(TILE_SIZE, TILE_SIZE);
    gfx.setDepth(1);
    this.tiles.set(id, { id, body, gfx, hp: TILE_HP, maxHp: TILE_HP, x, y, width: TILE_SIZE, height: TILE_SIZE });
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
    if (tile.gfx.texture.key !== textureKey) {
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
    tile.gfx.destroy();
    this.spawnDebris(tile.x, tile.y);
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
      tile.gfx.destroy();
    }
    this.tiles.clear();
    for (const d of this.debris) d.destroy();
    this.debris = [];
  }

  get tileCount(): number {
    return this.tiles.size;
  }
}
